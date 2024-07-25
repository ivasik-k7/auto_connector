import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError, RequestException, Timeout
from urllib3.util.retry import Retry

from app.utils import HttpMethod, config, setup_logger

logger = setup_logger(__name__, log_file="github_logs.log")


class HttpSessionFactory:
    @staticmethod
    def create_session(retries: int = 5, backoff_factor: int = 1) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        return session


class GitHubStatsService:
    """Connector for retrieving GitHub user statistics."""

    def get_top_language(self, username: str) -> str | None:
        url = (
            f"https://github-readme-stats.vercel.app/api/top-langs/"
            f"?username={username}&theme=vue-dark&show_icons=true&"
            f"hide_border=true&layout=compact&langs_count=1"
        )

        try:
            response = requests.request(HttpMethod.GET.value, url)
            response.raise_for_status()
            content = response.content.decode("utf-8")

            for line in content.splitlines():
                if "100.00%" in line:
                    return line.split("100.00%")[0].strip()

        except requests.RequestException as e:
            logger.error(f"Error retrieving top language for '{username}': {e}")
            return None


class GitHubActivityService:
    def __init__(self) -> None:
        self.api_url = "https://api.github.com"

    @property
    def headers(self):
        return {
            "Authorization": f"token {config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

    def _fetch_paginated_data(self, endpoint: str, method: HttpMethod) -> list[dict]:
        """
        Fetch paginated data from the GitHub API.

        :param endpoint: The API endpoint to fetch data from.
        :param method: HTTP method to use for the request.
        :return: List of data retrieved from all pages.
        """
        data = []
        page = 1
        per_page = 100
        url = self.api_url + endpoint

        while True:
            params = {"page": page, "per_page": per_page}
            response = requests.request(
                method=method.value,
                url=url,
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            page_data = response.json()

            if not page_data:
                break

            data.extend(page_data)
            page += 1

        return data

    def get_followers(self, username: str) -> list[dict]:
        """
        Get a list of followers for a given GitHub username.

        :param username: GitHub username to get followers for.
        :return: List of followers.
        """
        endpoint = f"/users/{username}/followers"
        return self._fetch_paginated_data(endpoint, HttpMethod.GET)

    def get_following(self, username: str) -> list[dict]:
        """
        Get a list of users that a given GitHub username is following.

        :param username: GitHub username to get followings for.
        :return: List of users that the given username is following.
        """
        endpoint = f"/users/{username}/following"
        return self._fetch_paginated_data(endpoint, HttpMethod.GET)


class GitHubConnectorService:
    def __init__(self):
        """
        Initialize the GitHubConnectorService.
        """
        self.api_url = "https://api.github.com/"

    @property
    def headers(self):
        return {
            "Authorization": f"token {config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

    def _execute_request(
        self,
        url: str,
        method: str = "GET",
        data: dict = None,
        params: dict = None,
        retries: int = 1,
        timeout: int = 5,
    ):
        """
        Execute an HTTP request with error handling and retries.

        :param url: The endpoint URL.
        :param method: The HTTP method (GET, POST, PUT, DELETE).
        :param data: The data to send with the request (for POST/PUT).
        :param params: URL parameters (for GET requests).
        :param retries: Number of retry attempts on failure.
        :param timeout: Timeout in seconds for the request.
        :return: Response object or None in case of failure.
        """
        composed_url = self.api_url + url
        attempt = 0
        while attempt < retries:
            try:
                response = requests.request(
                    method=method,
                    url=composed_url,
                    headers=self.headers,
                    data=data,
                    params=params,
                    timeout=timeout,
                )
                response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)
                return response
            except HTTPError as http_err:
                logger.error(f"HTTP error occurred: {http_err}")
            except Timeout as timeout_err:
                logger.error(f"Request timed out: {timeout_err}")
            except RequestException as req_err:
                logger.error(f"Request error occurred: {req_err}")
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")

            attempt += 1
            logger.info(f"Retrying... ({attempt}/{retries})")

        logger.error(f"Failed to execute request after {retries} attempts.")
        return None

    def follow(self, username):
        """
        Follow a user by their GitHub username.

        :param username: The username of the GitHub user to follow
        """
        endpoint = f"/user/following/{username}"
        response = self._execute_request(endpoint, HttpMethod.PUT)
        if response.status_code == 204:
            print(f"Successfully followed {username}")
        else:
            print(
                f"Failed to follow {username}: {response.status_code} {response.text}"
            )

    def unfollow(self, username):
        """
        Unfollow a user by their GitHub username.

        :param username: The username of the GitHub user to unfollow
        """
        endpoint = f"/user/following/{username}"
        response = self._execute_request(endpoint, HttpMethod.DELETE)
        if response.status_code == requests.status_codes:
            print(f"Successfully unfollow {username}")
        else:
            print(
                f"Failed to unfollow {username}: {response.status_code} {response.text}"
            )
