"""
Advanced GitHub Follower Sync with Enhanced Concurrency and Flexibility
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Set

from dotenv import load_dotenv

from app.services import GitHubActivityService, GitHubStatsService
from app.services.github import GitHubConnectorService
from app.utils import StorageManager, setup_logger, time_it
from app.utils.config import Config

load_dotenv()

try:
    config = Config.load(validate_with_github=True)
except (ValueError, SystemExit) as e:
    print(f"❌ Configuration error: {e}")
    sys.exit(1)

logger = setup_logger(__name__, log_file="follower_sync.log")


class ProcessingStrategy(Enum):
    """Strategy for processing followers."""

    FAST = "fast"  # Minimal data, maximum speed
    BALANCED = "balanced"  # Essential data with good performance
    COMPREHENSIVE = "comprehensive"  # Full enrichment, slower
    CUSTOM = "custom"  # User-defined fields


class FollowDecision(Enum):
    """Decision for following a user."""

    FOLLOW = "follow"
    SKIP = "skip"
    ALREADY_FOLLOWING = "already_following"
    ERROR = "error"


@dataclass
class ProcessingMetrics:
    """Metrics for tracking processing performance."""

    total_users: int = 0
    processed: int = 0
    failed: int = 0
    followed: int = 0
    skipped: int = 0
    already_following: int = 0
    start_time: float = field(default_factory=time.time)
    lock: Lock = field(default_factory=Lock)

    def increment(self, metric: str):
        with self.lock:
            setattr(self, metric, getattr(self, metric) + 1)

    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time

    @property
    def processing_rate(self) -> float:
        if self.elapsed_time == 0:
            return 0
        return self.processed / self.elapsed_time

    def summary(self) -> str:
        return (
            f"\n{'=' * 70}\n"
            f"📈 Processing Summary:\n"
            f"{'=' * 70}\n"
            f"  Total Users:        {self.total_users}\n"
            f"  Successfully Processed: {self.processed}\n"
            f"  Failed:             {self.failed}\n"
            f"  Followed:           {self.followed}\n"
            f"  Skipped:            {self.skipped}\n"
            f"  Already Following:  {self.already_following}\n"
            f"  Duration:           {self.elapsed_time:.2f}s\n"
            f"  Processing Rate:    {self.processing_rate:.2f} users/sec\n"
            f"{'=' * 70}\n"
        )


@dataclass
class UserProfile:
    """Enriched user profile data."""

    username: str
    id: Optional[int] = None

    # Basic info
    name: Optional[str] = None
    bio: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    email: Optional[str] = None
    blog: Optional[str] = None

    # Statistics
    public_repos: int = 0
    followers: int = 0
    following: int = 0

    # Technical
    top_language: Optional[str] = None
    language_stats: Dict[str, float] = field(default_factory=dict)

    # Social
    social_links: Dict[str, str] = field(default_factory=dict)

    # Contribution stats
    total_stars: int = 0
    total_forks: int = 0
    contribution_stats: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    created_at: Optional[str] = None
    url: Optional[str] = None
    avatar_url: Optional[str] = None

    # Processing metadata
    enrichment_level: str = "basic"
    processing_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "login": self.username,
            "name": self.name,
            "bio": self.bio[:200] if self.bio else "",
            "company": self.company,
            "location": self.location,
            "email": self.email,
            "blog": self.blog,
            "public_repos": self.public_repos,
            "followers": self.followers,
            "following": self.following,
            "top_language": self.top_language,
            "total_stars": self.total_stars,
            "total_forks": self.total_forks,
            "url": self.url,
            "created_at": self.created_at,
            "enrichment_level": self.enrichment_level,
            "processing_time": f"{self.processing_time:.2f}s",
        }


class UserEnricher:
    """Handles user profile enrichment with different strategies."""

    def __init__(self, stats_service: GitHubStatsService, strategy: ProcessingStrategy):
        self.stats_service = stats_service
        self.strategy = strategy
        self._cache: Dict[str, UserProfile] = {}
        self._cache_lock = Lock()

    def enrich_user(self, username: str, follower_data: Dict[str, Any]) -> UserProfile:
        """
        Enrich user profile based on processing strategy.

        Args:
            username: GitHub username
            follower_data: Basic follower data from API

        Returns:
            Enriched UserProfile
        """
        # Check cache
        with self._cache_lock:
            if username in self._cache:
                logger.debug(f"📦 Cache hit for {username}")
                return self._cache[username]

        start_time = time.time()

        profile = UserProfile(
            username=username,
            id=follower_data.get("id"),
            url=follower_data.get("html_url", f"https://github.com/{username}"),
            avatar_url=follower_data.get("avatar_url"),
        )

        try:
            if self.strategy == ProcessingStrategy.FAST:
                profile.enrichment_level = "fast"
                # Just get top language
                profile.top_language = self.stats_service.get_top_language(username)

            elif self.strategy == ProcessingStrategy.BALANCED:
                profile.enrichment_level = "balanced"
                # Get basic details and top language
                details = self.stats_service.get_user_details(username)
                if details:
                    self._populate_basic_details(profile, details)
                profile.top_language = self.stats_service.get_top_language(username)

            elif self.strategy == ProcessingStrategy.COMPREHENSIVE:
                profile.enrichment_level = "comprehensive"
                # Full enrichment
                enriched = self.stats_service.get_enriched_profile(username)
                if enriched.get("basic_info"):
                    self._populate_basic_details(profile, enriched["basic_info"])
                profile.top_language = enriched.get("top_language")
                profile.language_stats = enriched.get("language_stats", {})
                profile.contribution_stats = enriched.get("contribution_stats", {})

                # Extract additional stats
                contrib_stats = profile.contribution_stats
                profile.total_stars = contrib_stats.get("total_stars", 0)
                profile.total_forks = contrib_stats.get("total_forks", 0)

        except Exception as e:
            logger.warning(f"Enrichment failed for {username}: {e}")

        profile.processing_time = time.time() - start_time

        # Cache the result
        with self._cache_lock:
            self._cache[username] = profile

        return profile

    def _populate_basic_details(self, profile: UserProfile, details: Dict[str, Any]):
        """Populate profile with basic user details."""
        profile.name = details.get("name")
        profile.bio = details.get("bio")
        profile.company = details.get("company")
        profile.location = details.get("location")
        profile.email = details.get("email")
        profile.blog = details.get("blog")
        profile.public_repos = details.get("public_repos", 0)
        profile.followers = details.get("followers", 0)
        profile.following = details.get("following", 0)
        profile.created_at = details.get("created_at")
        profile.social_links = details.get("social_links", {})

    def batch_enrich(
        self, followers: List[Dict[str, Any]], max_workers: int = 10
    ) -> List[UserProfile]:
        """
        Enrich multiple users concurrently.

        Args:
            followers: List of follower data
            max_workers: Maximum concurrent workers

        Returns:
            List of enriched profiles
        """
        profiles = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self.enrich_user, follower.get("login"), follower
                ): follower
                for follower in followers
                if follower.get("login")
            }

            for future in as_completed(futures):
                try:
                    profile = future.result()
                    profiles.append(profile)
                except Exception as e:
                    follower = futures[future]
                    logger.error(
                        f"Batch enrichment failed for {follower.get('login')}: {e}"
                    )

        return profiles


class FollowFilter:
    """Advanced filtering system for follow decisions."""

    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get("enabled", False)
        self.whitelist = set(config.get("whitelist", []))
        self.blacklist = set(config.get("blacklist", []))
        self.languages = (
            set(config.get("languages", [])) if config.get("languages") else None
        )
        self.min_repos = config.get("min_repos", 0)
        self.max_repos = config.get("max_repos", float("inf"))
        self.min_followers = config.get("min_followers", 0)
        self.max_followers = config.get("max_followers", float("inf"))
        self.min_following = config.get("min_following", 0)
        self.required_keywords = set(config.get("required_keywords", []))
        self.exclude_keywords = set(config.get("exclude_keywords", []))
        self.min_account_age_days = config.get("min_account_age_days", 0)
        self.custom_filter: Optional[Callable[[UserProfile], bool]] = None

    def should_follow(self, profile: UserProfile) -> tuple[bool, str]:
        """
        Determine if user should be followed.

        Args:
            profile: User profile to evaluate

        Returns:
            Tuple of (should_follow, reason)
        """
        if not self.enabled:
            return False, "Auto-follow disabled"

        # Whitelist takes priority
        if self.whitelist and profile.username in self.whitelist:
            return True, "Whitelisted user"

        # Blacklist check
        if profile.username in self.blacklist:
            return False, "Blacklisted user"

        # Language filter
        if self.languages and profile.top_language not in self.languages:
            return False, f"Language mismatch: {profile.top_language}"

        # Repository count filter
        if not (self.min_repos <= profile.public_repos <= self.max_repos):
            return False, f"Repo count: {profile.public_repos}"

        # Follower count filter
        if not (self.min_followers <= profile.followers <= self.max_followers):
            return False, f"Follower count: {profile.followers}"

        # Following count filter
        if profile.following < self.min_following:
            return False, f"Following count: {profile.following}"

        # Keyword filters
        bio_lower = (profile.bio or "").lower()
        if self.required_keywords:
            if not any(kw.lower() in bio_lower for kw in self.required_keywords):
                return False, "Missing required keywords"

        if self.exclude_keywords:
            if any(kw.lower() in bio_lower for kw in self.exclude_keywords):
                return False, "Contains excluded keywords"

        # Account age filter
        if self.min_account_age_days > 0 and profile.created_at:
            try:
                from datetime import datetime

                created = datetime.fromisoformat(
                    profile.created_at.replace("Z", "+00:00")
                )
                age_days = (datetime.now(created.tzinfo) - created).days
                if age_days < self.min_account_age_days:
                    return False, f"Account too new: {age_days} days"
            except Exception as e:
                logger.debug(f"Could not parse account age: {e}")

        # Custom filter
        if self.custom_filter:
            try:
                if not self.custom_filter(profile):
                    return False, "Custom filter rejected"
            except Exception as e:
                logger.error(f"Custom filter error: {e}")
                return False, "Custom filter error"

        return True, "All filters passed"


class FollowerProcessor:
    """Main processor orchestrating follower sync operations."""

    def __init__(
        self,
        activity_service: GitHubActivityService,
        stats_service: GitHubStatsService,
        connector_service: GitHubConnectorService,
        config: Config,
        strategy: ProcessingStrategy = ProcessingStrategy.BALANCED,
    ):
        self.activity_service = activity_service
        self.stats_service = stats_service
        self.connector_service = connector_service
        self.config = config
        self.strategy = strategy

        self.enricher = UserEnricher(stats_service, strategy)
        self.metrics = ProcessingMetrics()

        # Load follow configuration
        follow_config = getattr(config, "FOLLOW_CONFIG", {"enabled": False})
        self.follow_filter = FollowFilter(follow_config)

        # Track already following to avoid duplicate API calls
        self._following_cache: Set[str] = set()
        self._following_cache_lock = Lock()

    def process_follower(
        self, follower: Dict[str, Any], file_manager: StorageManager
    ) -> Optional[UserProfile]:
        """
        Process a single follower with enrichment and follow decision.

        Args:
            follower: Follower data from GitHub API
            file_manager: Storage manager for persistence

        Returns:
            Processed UserProfile or None on failure
        """
        username = follower.get("login")
        if not username:
            logger.error("Follower missing 'login' field")
            self.metrics.increment("failed")
            return None

        try:
            # Enrich user profile
            profile = self.enricher.enrich_user(username, follower)

            # Make follow decision
            if self.follow_filter.enabled:
                decision, reason = self._make_follow_decision(profile)
                self._handle_follow_decision(decision, username, reason)

            # Save to storage
            file_manager.add(profile.to_dict())

            self.metrics.increment("processed")
            logger.info(
                f"✅ Processed {username} "
                f"({self.metrics.processed}/{self.metrics.total_users}) "
                f"[{profile.processing_time:.2f}s]"
            )

            return profile

        except Exception as e:
            logger.error(f"❌ Failed to process {username}: {e}", exc_info=True)
            self.metrics.increment("failed")
            return None

    def _make_follow_decision(self, profile: UserProfile) -> tuple[FollowDecision, str]:
        """Make decision about following a user."""
        # Check if already following
        with self._following_cache_lock:
            if profile.username in self._following_cache:
                return FollowDecision.ALREADY_FOLLOWING, "Already following"

        # Apply filters
        should_follow, reason = self.follow_filter.should_follow(profile)

        if should_follow:
            return FollowDecision.FOLLOW, reason
        else:
            return FollowDecision.SKIP, reason

    def _handle_follow_decision(
        self, decision: FollowDecision, username: str, reason: str
    ):
        """Handle the follow decision."""
        if decision == FollowDecision.FOLLOW:
            try:
                if self.connector_service.follow(username):
                    with self._following_cache_lock:
                        self._following_cache.add(username)
                    self.metrics.increment("followed")
                    logger.info(f"👥 Followed {username}: {reason}")
                else:
                    self.metrics.increment("failed")
            except Exception as e:
                logger.error(f"Follow failed for {username}: {e}")
                self.metrics.increment("failed")

        elif decision == FollowDecision.SKIP:
            self.metrics.increment("skipped")
            logger.debug(f"⏭️  Skipped {username}: {reason}")

        elif decision == FollowDecision.ALREADY_FOLLOWING:
            self.metrics.increment("already_following")
            logger.debug(f"✓ Already following {username}")

    def load_existing_following(self):
        """Pre-load list of users we're already following."""
        try:
            logger.info("📥 Loading existing following list...")
            # Get authenticated user
            response = self.activity_service._execute_request("user")
            if response and response.status_code == 200:
                current_user = response.json()["login"]
                following = self.activity_service.get_following(current_user)

                with self._following_cache_lock:
                    self._following_cache = {u["login"] for u in following}

                logger.info(f"✅ Loaded {len(self._following_cache)} existing follows")
        except Exception as e:
            logger.warning(f"Could not load following list: {e}")

    def process_organization(
        self, org: str, file_manager: StorageManager, max_workers: Optional[int] = None
    ):
        """
        Process all followers from an organization.

        Args:
            org: Organization name
            file_manager: Storage manager
            max_workers: Override default max workers
        """
        try:
            logger.info(f"📊 Fetching followers for: {org}")
            followers = self.activity_service.get_followers(org)

            if not followers:
                logger.warning(f"No followers found for {org}")
                return

            logger.info(f"✅ Found {len(followers)} followers for {org}")
            self.metrics.total_users += len(followers)

            # Process concurrently
            workers = max_workers or self.config.MAX_WORKERS
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        self.process_follower, follower, file_manager
                    ): follower
                    for follower in reversed(followers)
                }

                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Executor error: {e}", exc_info=True)
                        self.metrics.increment("failed")

        except Exception as e:
            logger.error(f"❌ Error processing organization {org}: {e}", exc_info=True)


@time_it
def main():
    """
    Main execution function with advanced configuration.
    """
    # Initialize services
    activity_service = GitHubActivityService()
    stats_service = GitHubStatsService()
    connector = GitHubConnectorService()

    # Configuration
    strategy = ProcessingStrategy(getattr(config, "PROCESSING_STRATEGY", "balanced"))
    organizations = getattr(config, "TARGET_ORGANIZATIONS", ["ivasik-k7"])
    output_file = getattr(config, "OUTPUT_FILE", "examples/profiles.csv")

    logger.info(f"🚀 Starting Advanced Follower Sync")
    logger.info(f"   Strategy: {strategy.value}")
    logger.info(f"   Organizations: {organizations}")
    logger.info(f"   Max Workers: {config.MAX_WORKERS}")

    # Initialize processor
    processor = FollowerProcessor(
        activity_service, stats_service, connector, config, strategy
    )

    # Pre-load following list to avoid duplicate follows
    processor.load_existing_following()

    # Process all organizations
    with StorageManager(output_file) as file_manager:
        for org in organizations:
            processor.process_organization(org, file_manager)

    # Print summary
    logger.info(processor.metrics.summary())

    return processor.metrics


if __name__ == "__main__":
    try:
        metrics = main()
        sys.exit(0 if metrics.failed == 0 else 1)
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Process interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
