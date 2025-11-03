import re
import time
from dataclasses import dataclass
from enum import Enum
from http import HTTPStatus
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError, RequestException, Timeout
from urllib3.util.retry import Retry

from app.utils import config, setup_logger

logger = setup_logger(__name__, log_file="github_logs.log")


class HttpMethod(Enum):
    """HTTP methods enum."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class RateLimitInfo:
    """Rate limit information from GitHub API."""

    limit: int
    remaining: int
    reset_time: int

    @property
    def is_exhausted(self) -> bool:
        return self.remaining == 0

    @property
    def seconds_until_reset(self) -> int:
        return max(0, self.reset_time - int(time.time()))


class GitHubAPIException(Exception):
    """Base exception for GitHub API errors."""

    pass


class RateLimitExceeded(GitHubAPIException):
    """Raised when rate limit is exceeded."""

    pass


class HttpSessionFactory:
    """Factory for creating configured HTTP sessions."""

    @staticmethod
    def create_session(
        retries: int = 5, backoff_factor: float = 1.0, timeout: int = 30
    ) -> requests.Session:
        """
        Create a requests session with retry strategy.

        Args:
            retries: Number of retry attempts
            backoff_factor: Backoff multiplier for retries
            timeout: Default timeout for requests

        Returns:
            Configured requests.Session
        """
        session = requests.Session()

        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
            raise_on_status=False,
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy, pool_connections=10, pool_maxsize=20
        )

        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session


class BaseGitHubService:
    """Base service with common GitHub API functionality."""

    def __init__(self, api_url: str = "https://api.github.com"):
        self.api_url = api_url.rstrip("/")
        self.session = HttpSessionFactory.create_session()
        self._rate_limit_info: Optional[RateLimitInfo] = None

    @property
    def headers(self) -> Dict[str, str]:
        """Get headers for GitHub API requests."""
        return {
            "Authorization": f"token {config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Follower-Sync/1.0",
        }

    def _update_rate_limit_info(self, response: requests.Response) -> None:
        """Update rate limit information from response headers."""
        try:
            self._rate_limit_info = RateLimitInfo(
                limit=int(response.headers.get("X-RateLimit-Limit", 0)),
                remaining=int(response.headers.get("X-RateLimit-Remaining", 0)),
                reset_time=int(response.headers.get("X-RateLimit-Reset", 0)),
            )

            if self._rate_limit_info.remaining < 100:
                logger.warning(
                    f"⚠️  Rate limit low: {self._rate_limit_info.remaining} "
                    f"requests remaining"
                )
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse rate limit headers: {e}")

    def _handle_rate_limit(self) -> None:
        """Handle rate limit by waiting if necessary."""
        if self._rate_limit_info and self._rate_limit_info.is_exhausted:
            wait_time = self._rate_limit_info.seconds_until_reset + 5
            logger.warning(f"⏳ Rate limit exceeded. Waiting {wait_time} seconds...")
            time.sleep(wait_time)

    def _execute_request(
        self,
        endpoint: str,
        method: HttpMethod = HttpMethod.GET,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        retry_on_rate_limit: bool = True,
    ) -> Optional[requests.Response]:
        """
        Execute an HTTP request with comprehensive error handling.

        Args:
            endpoint: API endpoint (without base URL)
            method: HTTP method
            data: Request body data
            params: URL parameters
            timeout: Request timeout in seconds
            retry_on_rate_limit: Whether to wait and retry on rate limit

        Returns:
            Response object or None on failure

        Raises:
            GitHubAPIException: On API errors
            RateLimitExceeded: If rate limit exceeded and retry disabled
        """
        url = f"{self.api_url}/{endpoint.lstrip('/')}"

        try:
            if retry_on_rate_limit:
                self._handle_rate_limit()

            logger.debug(f"🔍 {method.value} {url}")

            response = self.session.request(
                method=method.value,
                url=url,
                headers=self.headers,
                json=data,
                params=params,
                timeout=timeout,
            )

            self._update_rate_limit_info(response)

            if response.status_code == 429:
                if retry_on_rate_limit:
                    logger.warning("⚠️  Rate limited, waiting and retrying...")
                    time.sleep(60)
                    return self._execute_request(
                        endpoint, method, data, params, timeout, retry_on_rate_limit
                    )
                else:
                    raise RateLimitExceeded("GitHub API rate limit exceeded")

            response.raise_for_status()

            return response

        except HTTPError as e:
            logger.error(f"❌ HTTP error for {url}: {e}")
            if e.response is not None:
                logger.error(f"Response body: {e.response.text}")
            raise GitHubAPIException(f"HTTP error: {e}") from e

        except Timeout as e:
            logger.error(f"⏱️  Request timeout for {url}: {e}")
            raise GitHubAPIException(f"Request timeout: {e}") from e

        except RequestException as e:
            logger.error(f"❌ Request error for {url}: {e}")
            raise GitHubAPIException(f"Request error: {e}") from e

        except Exception as e:
            logger.error(f"❌ Unexpected error for {url}: {e}", exc_info=True)
            raise GitHubAPIException(f"Unexpected error: {e}") from e

    def get_rate_limit_status(self) -> Optional[RateLimitInfo]:
        """Get current rate limit information."""
        return self._rate_limit_info


class GitHubStatsService(BaseGitHubService):
    """Service for retrieving GitHub user statistics using multiple sources."""

    def __init__(self):
        super().__init__()
        # Multiple open-source stats services
        self.stats_services = [
            "https://github-readme-stats.vercel.app/api",
            "https://github-readme-stats-git-masterrstaa-rickstaa.vercel.app/api",
        ]

    def get_top_language(self, username: str) -> Optional[str]:
        """
        Get the top programming language for a user using github-readme-stats.

        Args:
            username: GitHub username

        Returns:
            Top language or None if unavailable
        """
        for stats_base_url in self.stats_services:
            try:
                url = (
                    f"{stats_base_url}/top-langs/"
                    f"?username={username}&theme=vue-dark&show_icons=true&"
                    f"hide_border=true&layout=compact&langs_count=1"
                )

                response = requests.get(url, timeout=10)
                response.raise_for_status()
                content = response.content.decode("utf-8")

                # Parse SVG content for language
                for line in content.splitlines():
                    if "100.00%" in line:
                        language = line.split("100.00%")[0].strip()
                        logger.debug(f"Top language for {username}: {language}")
                        return language

                logger.debug(f"No language data found for {username}")
                return None

            except requests.RequestException as e:
                logger.debug(f"Stats service {stats_base_url} failed: {e}")
                continue

        logger.warning(f"All stats services failed for '{username}'")
        return None

    def get_language_stats(self, username: str) -> Dict[str, float]:
        """
        Calculate language statistics from user's repositories.

        Args:
            username: GitHub username

        Returns:
            Dictionary with language percentages
        """
        try:
            repos = self.get_user_repos(username, limit=100)
            language_bytes = {}

            for repo in repos:
                if repo.get("fork", False):
                    continue

                # Get language stats for each repo
                languages_url = repo.get("languages_url")
                if languages_url:
                    try:
                        response = requests.get(
                            languages_url, headers=self.headers, timeout=10
                        )
                        if response.status_code == HTTPStatus.OK:
                            lang_data = response.json()
                            for lang, bytes_count in lang_data.items():
                                language_bytes[lang] = (
                                    language_bytes.get(lang, 0) + bytes_count
                                )
                    except Exception:
                        continue

            # Calculate percentages
            total_bytes = sum(language_bytes.values())
            if total_bytes == 0:
                return {}

            language_stats = {
                lang: round((bytes_count / total_bytes) * 100, 2)
                for lang, bytes_count in language_bytes.items()
            }

            return dict(
                sorted(language_stats.items(), key=lambda x: x[1], reverse=True)
            )

        except Exception as e:
            logger.warning(f"Could not calculate language stats for '{username}': {e}")
            return {}

    def get_user_details(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive user details from GitHub API with enrichment.

        Args:
            username: GitHub username

        Returns:
            Dictionary with enriched user details or None on failure
        """
        try:
            response = self._execute_request(f"users/{username}")
            if not response or response.status_code != HTTPStatus.OK:
                return None

            data = response.json()

            # Extract email from events if not public
            email = data.get("email")
            if not email:
                email = self._extract_email_from_events(username)

            # Parse social links from bio
            social_links = self._extract_social_links(data.get("bio", ""))

            user_details = {
                "login": data.get("login"),
                "id": data.get("id"),
                "name": data.get("name"),
                "bio": data.get("bio"),
                "company": data.get("company"),
                "location": data.get("location"),
                "email": email,
                "blog": data.get("blog"),
                "twitter_username": data.get("twitter_username"),
                "public_repos": data.get("public_repos", 0),
                "public_gists": data.get("public_gists", 0),
                "followers": data.get("followers", 0),
                "following": data.get("following", 0),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "html_url": data.get("html_url"),
                "avatar_url": data.get("avatar_url"),
                "hireable": data.get("hireable"),
                "type": data.get("type"),
                "site_admin": data.get("site_admin"),
                "social_links": social_links,
            }

            logger.debug(f"Retrieved details for {username}")
            return user_details

        except GitHubAPIException as e:
            logger.warning(f"Could not retrieve user details for '{username}': {e}")
            return None

    def _extract_email_from_events(self, username: str) -> Optional[str]:
        """
        Try to extract email from user's public events.

        Args:
            username: GitHub username

        Returns:
            Email address or None
        """
        try:
            response = self._execute_request(f"users/{username}/events/public")
            if not response or response.status_code != HTTPStatus.OK:
                return None

            events = response.json()
            for event in events[:10]:  # Check first 10 events
                if event.get("type") == "PushEvent":
                    commits = event.get("payload", {}).get("commits", [])
                    for commit in commits:
                        author = commit.get("author", {})
                        email = author.get("email")
                        if email and not email.endswith("@users.noreply.github.com"):
                            logger.debug(f"Found email for {username}: {email}")
                            return email

            return None

        except Exception as e:
            logger.debug(f"Could not extract email from events for {username}: {e}")
            return None

    def _extract_social_links(self, bio: Optional[str]) -> Dict[str, str]:
        """
        Extract social media links from bio.

        Args:
            bio: User's bio text

        Returns:
            Dictionary with social platform names and links
        """
        if not bio:
            return {}

        social_links = {}

        # Patterns for common social platforms
        patterns = {
            "twitter": r"twitter\.com/([a-zA-Z0-9_]+)",
            "linkedin": r"linkedin\.com/in/([a-zA-Z0-9-]+)",
            "telegram": r"t\.me/([a-zA-Z0-9_]+)",
            "discord": r"discord\.gg/([a-zA-Z0-9]+)",
            "youtube": r"youtube\.com/(@?[a-zA-Z0-9_-]+)",
            "medium": r"medium\.com/@([a-zA-Z0-9_-]+)",
            "dev.to": r"dev\.to/([a-zA-Z0-9_-]+)",
            "stackoverflow": r"stackoverflow\.com/users/(\d+)",
        }

        for platform, pattern in patterns.items():
            match = re.search(pattern, bio, re.IGNORECASE)
            if match:
                social_links[platform] = match.group(0)

        return social_links

    def get_user_repos(
        self, username: str, sort: str = "updated", limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get user's public repositories.

        Args:
            username: GitHub username
            sort: Sort order (created, updated, pushed, full_name)
            limit: Maximum number of repos to return

        Returns:
            List of repository dictionaries
        """
        try:
            params = {"sort": sort, "per_page": min(limit or 100, 100)}
            response = self._execute_request(f"users/{username}/repos", params=params)

            if response and response.status_code == HTTPStatus.OK:
                repos = response.json()
                if limit:
                    repos = repos[:limit]
                logger.debug(f"Retrieved {len(repos)} repos for {username}")
                return repos

            return []

        except GitHubAPIException as e:
            logger.warning(f"Could not retrieve repos for '{username}': {e}")
            return []

    def get_contribution_stats(self, username: str) -> Dict[str, Any]:
        """
        Get comprehensive contribution statistics.

        Args:
            username: GitHub username

        Returns:
            Dictionary with contribution statistics
        """
        try:
            repos = self.get_user_repos(username, limit=100)

            stats = {
                "total_repos": 0,
                "original_repos": 0,
                "forked_repos": 0,
                "total_stars": 0,
                "total_forks": 0,
                "total_watchers": 0,
                "languages": set(),
                "topics": set(),
                "has_wiki": 0,
                "has_pages": 0,
                "has_projects": 0,
            }

            for repo in repos:
                stats["total_repos"] += 1

                if repo.get("fork", False):
                    stats["forked_repos"] += 1
                else:
                    stats["original_repos"] += 1

                stats["total_stars"] += repo.get("stargazers_count", 0)
                stats["total_forks"] += repo.get("forks_count", 0)
                stats["total_watchers"] += repo.get("watchers_count", 0)

                if repo.get("language"):
                    stats["languages"].add(repo["language"])

                topics = repo.get("topics", [])
                stats["topics"].update(topics)

                if repo.get("has_wiki"):
                    stats["has_wiki"] += 1
                if repo.get("has_pages"):
                    stats["has_pages"] += 1
                if repo.get("has_projects"):
                    stats["has_projects"] += 1

            # Convert sets to lists for JSON serialization
            stats["languages"] = list(stats["languages"])
            stats["topics"] = list(stats["topics"])[:20]  # Top 20 topics

            return stats

        except Exception as e:
            logger.warning(
                f"Could not calculate contribution stats for '{username}': {e}"
            )
            return {}

    def get_enriched_profile(self, username: str) -> Dict[str, Any]:
        """
        Get fully enriched user profile with all available data.

        Args:
            username: GitHub username

        Returns:
            Comprehensive user profile dictionary
        """
        logger.info(f"🔍 Enriching profile for: {username}")

        profile = {
            "username": username,
            "basic_info": None,
            "top_language": None,
            "language_stats": {},
            "contribution_stats": {},
            "recent_activity": None,
            "enrichment_timestamp": time.time(),
        }

        # Get basic user details
        try:
            profile["basic_info"] = self.get_user_details(username)
        except Exception as e:
            logger.error(f"Failed to get basic info for {username}: {e}")

        # Get top language
        try:
            profile["top_language"] = self.get_top_language(username)
        except Exception as e:
            logger.debug(f"Failed to get top language for {username}: {e}")

        # Get detailed language stats
        try:
            profile["language_stats"] = self.get_language_stats(username)
        except Exception as e:
            logger.debug(f"Failed to get language stats for {username}: {e}")

        # Get contribution statistics
        try:
            profile["contribution_stats"] = self.get_contribution_stats(username)
        except Exception as e:
            logger.debug(f"Failed to get contribution stats for {username}: {e}")

        logger.info(f"✅ Profile enrichment complete for: {username}")
        return profile


class GitHubActivityService(BaseGitHubService):
    """Service for GitHub social activity (followers, following)."""

    def _fetch_paginated_data(
        self,
        endpoint: str,
        method: HttpMethod = HttpMethod.GET,
        per_page: int = 100,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch paginated data from the GitHub API.

        Args:
            endpoint: The API endpoint
            method: HTTP method
            per_page: Results per page (max 100)
            max_pages: Maximum number of pages to fetch

        Returns:
            List of all retrieved data
        """
        data = []
        page = 1

        while True:
            if max_pages and page > max_pages:
                logger.info(f"Reached max pages limit: {max_pages}")
                break

            try:
                params = {"page": page, "per_page": min(per_page, 100)}
                response = self._execute_request(endpoint, method, params=params)

                if not response or response.status_code != HTTPStatus.OK:
                    break

                page_data = response.json()

                if not page_data:
                    logger.debug(f"No more data on page {page}")
                    break

                data.extend(page_data)
                logger.debug(f"Fetched page {page}: {len(page_data)} items")
                page += 1

                # Check if there are more pages via Link header
                if "Link" not in response.headers:
                    break
                if 'rel="next"' not in response.headers.get("Link", ""):
                    break

            except GitHubAPIException as e:
                logger.error(f"Error fetching page {page}: {e}")
                break

        logger.info(f"Total items fetched: {len(data)}")
        return data

    def get_followers(
        self, username: str, max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get followers for a user.

        Args:
            username: GitHub username
            max_pages: Maximum number of pages to fetch

        Returns:
            List of follower dictionaries
        """
        logger.info(f"📥 Fetching followers for: {username}")
        endpoint = f"users/{username}/followers"
        return self._fetch_paginated_data(endpoint, max_pages=max_pages)

    def get_following(
        self, username: str, max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get users that a user is following.

        Args:
            username: GitHub username
            max_pages: Maximum number of pages to fetch

        Returns:
            List of following user dictionaries
        """
        logger.info(f"📤 Fetching following for: {username}")
        endpoint = f"users/{username}/following"
        return self._fetch_paginated_data(endpoint, max_pages=max_pages)

    def is_following(self, username: str, target_username: str) -> bool:
        """
        Check if a user is following another user.

        Args:
            username: GitHub username (follower)
            target_username: Target username (followee)

        Returns:
            True if following, False otherwise
        """
        try:
            endpoint = f"users/{username}/following/{target_username}"
            response = self._execute_request(endpoint)
            return response and response.status_code == HTTPStatus.NO_CONTENT
        except GitHubAPIException:
            return False


class GitHubConnectorService(BaseGitHubService):
    """Service for GitHub user interactions (follow, unfollow)."""

    def follow(self, username: str) -> bool:
        """
        Follow a user by their GitHub username.

        Args:
            username: The username of the GitHub user to follow

        Returns:
            True if successful, False otherwise
        """
        try:
            endpoint = f"user/following/{username}"
            response = self._execute_request(endpoint, HttpMethod.PUT)

            return response and response.status_code == HTTPStatus.NO_CONTENT
        except GitHubAPIException as e:
            logger.error(f"❌ Error following {username}: {e}")
            return False

    def unfollow(self, username: str) -> bool:
        """
        Unfollow a user by their GitHub username.

        Args:
            username: The username of the GitHub user to unfollow

        Returns:
            True if successful, False otherwise
        """
        try:
            endpoint = f"user/following/{username}"
            response = self._execute_request(endpoint, HttpMethod.DELETE)

            if response and response.status_code == HTTPStatus.NO_CONTENT:
                logger.info(f"✅ Successfully unfollowed {username}")
                return True
            else:
                status = response.status_code if response else "No response"
                logger.warning(f"⚠️  Failed to unfollow {username}: {status}")
                return False

        except GitHubAPIException as e:
            logger.error(f"❌ Error unfollowing {username}: {e}")
            return False

    def batch_follow(self, usernames: List[str], delay: float = 1.0) -> Dict[str, bool]:
        """
        Follow multiple users with rate limiting.

        Args:
            usernames: List of usernames to follow
            delay: Delay between requests in seconds

        Returns:
            Dictionary mapping username to success status
        """
        results = {}

        for username in usernames:
            results[username] = self.follow(username)
            if delay > 0:
                time.sleep(delay)

        success_count = sum(1 for v in results.values() if v)
        logger.info(
            f"📊 Batch follow complete: {success_count}/{len(usernames)} successful"
        )

        return results

    def batch_unfollow(
        self, usernames: List[str], delay: float = 1.0
    ) -> Dict[str, bool]:
        """
        Unfollow multiple users with rate limiting.

        Args:
            usernames: List of usernames to unfollow
            delay: Delay between requests in seconds

        Returns:
            Dictionary mapping username to success status
        """
        results = {}

        for username in usernames:
            results[username] = self.unfollow(username)
            if delay > 0:
                time.sleep(delay)

        success_count = sum(1 for v in results.values() if v)
        logger.info(
            f"📊 Batch unfollow complete: {success_count}/{len(usernames)} successful"
        )

        return results
