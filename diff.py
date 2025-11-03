import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from dotenv import load_dotenv

from app.services import GitHubActivityService, GitHubConnectorService
from app.utils import setup_logger, time_it
from app.utils.config import Config

load_dotenv()

try:
    config = Config.load(validate_with_github=True)
except (ValueError, SystemExit) as e:
    print(f"❌ Configuration error: {e}")
    sys.exit(1)

logger = setup_logger(__name__, log_file=config.LOG_FILE, level=config.LOG_LEVEL)


@dataclass
class DiffMetrics:
    """Metrics for tracking diff operations."""

    total_following: int = 0
    total_followers: int = 0
    non_reciprocal: int = 0
    unfollowed: int = 0
    failed_unfollows: int = 0
    skipped_whitelist: int = 0
    skipped_filters: int = 0
    start_time: float = field(default_factory=time.time)

    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time

    def summary(self) -> str:
        reciprocal_rate = (
            (self.total_following - self.non_reciprocal) / self.total_following * 100
            if self.total_following > 0
            else 0
        )

        return (
            f"\n{'=' * 70}\n"
            f"📊 Follow Diff Summary:\n"
            f"{'=' * 70}\n"
            f"  Total Following:         {self.total_following}\n"
            f"  Total Followers:         {self.total_followers}\n"
            f"  Non-reciprocal:          {self.non_reciprocal}\n"
            f"  Skipped (whitelist):     {self.skipped_whitelist}\n"
            f"  Skipped (filters):       {self.skipped_filters}\n"
            f"  Successfully Unfollowed: {self.unfollowed}\n"
            f"  Failed Unfollows:        {self.failed_unfollows}\n"
            f"  Duration:                {self.elapsed_time:.2f}s\n"
            f"  Reciprocal Rate:         {reciprocal_rate:.1f}%\n"
            f"{'=' * 70}\n"
        )


class FollowDiffAnalyzer:
    """
    Analyzes follow relationships and manages unfollow operations.
    Designed for automated CI/CD execution.
    """

    def __init__(
        self,
        activity_service: GitHubActivityService,
        connector_service: GitHubConnectorService,
        config: Config,
    ):
        self.activity_service = activity_service
        self.connector_service = connector_service
        self.config = config
        self.metrics = DiffMetrics()

        # Cache for API results
        self._following_cache: List[Dict] = []
        self._followers_cache: List[Dict] = []
        self._current_user: Optional[str] = None

    def get_current_user(self) -> str:
        """Get the authenticated user's login."""
        if not self._current_user:
            try:
                response = self.activity_service._execute_request("user")
                if response and response.status_code == 200:
                    self._current_user = response.json()["login"]
                else:
                    raise ValueError("Could not fetch current user info")
            except Exception as e:
                logger.error(f"❌ Failed to get current user: {e}")
                raise
        return self._current_user

    def load_follow_data(self) -> None:
        """Load following and followers data."""
        try:
            current_user = self.get_current_user()
            logger.info(f"👤 Loading follow data for: {current_user}")

            # Load following
            logger.info("📥 Loading users you follow...")
            self._following_cache = self.activity_service.get_following(current_user)
            self.metrics.total_following = len(self._following_cache)
            logger.info(f"✅ Loaded {self.metrics.total_following} users you follow")

            # Load followers
            logger.info("📥 Loading your followers...")
            self._followers_cache = self.activity_service.get_followers(current_user)
            self.metrics.total_followers = len(self._followers_cache)
            logger.info(f"✅ Loaded {self.metrics.total_followers} followers")

        except Exception as e:
            logger.error(f"❌ Failed to load follow data: {e}")
            raise

    def find_non_reciprocal_users(self) -> List[Dict]:
        """
        Find users you follow who don't follow you back.

        Returns:
            List of user dicts who don't follow back
        """
        if not self._following_cache or not self._followers_cache:
            self.load_follow_data()

        # Create sets for efficient lookup
        following_usernames = {user["login"].lower() for user in self._following_cache}
        followers_usernames = {user["login"].lower() for user in self._followers_cache}

        # Find users you follow who don't follow you back
        non_reciprocal = [
            user
            for user in self._following_cache
            if user["login"].lower() not in followers_usernames
        ]

        self.metrics.non_reciprocal = len(non_reciprocal)

        logger.info(f"🔍 Found {self.metrics.non_reciprocal} non-reciprocal follows")
        return non_reciprocal

    def unfollow_user(self, username: str) -> bool:
        """
        Unfollow a single user.

        Args:
            username: GitHub username to unfollow

        Returns:
            True if successful, False otherwise
        """
        try:
            # Use configurable delay between follows
            if self.config.FOLLOW_CONFIG.get("delay_between_follows"):
                time.sleep(self.config.FOLLOW_CONFIG["delay_between_follows"])

            success = self.connector_service.unfollow(username)
            if success:
                self.metrics.unfollowed += 1
                logger.info(f"❌ Unfollowed: {username}")
            else:
                self.metrics.failed_unfollows += 1
                logger.error(f"⚠️  Failed to unfollow: {username}")
            return success

        except Exception as e:
            self.metrics.failed_unfollows += 1
            logger.error(f"❌ Error unfollowing {username}: {e}")
            return False

    def batch_unfollow(
        self,
        users: List[Dict],
        dry_run: bool = False,
    ) -> None:
        """
        Unfollow multiple users concurrently.

        Args:
            users: List of user dicts to unfollow
            dry_run: If True, only simulate without actual unfollowing
        """
        if not users:
            logger.info("✅ No users to unfollow")
            return

        if dry_run:
            logger.info("🧪 DRY RUN MODE - No actual unfollows will be performed")

        workers = self.config.MAX_WORKERS
        batch_size = self.config.BATCH_SIZE

        # Apply safety limits from config
        max_unfollows = self.config.MAX_FOLLOWS_PER_RUN
        if len(users) > max_unfollows:
            logger.warning(
                f"⚠️  Limiting unfollows to {max_unfollows} (config: MAX_FOLLOWS_PER_RUN)"
            )
            users = users[:max_unfollows]

        logger.info(
            f"🚀 Starting batch unfollow for {len(users)} users (workers: {workers})"
        )

        # Process in batches if configured
        if self.config.PROCESS_IN_BATCHES:
            for i in range(0, len(users), batch_size):
                batch = users[i : i + batch_size]
                logger.info(
                    f"📦 Processing batch {i // batch_size + 1}/{(len(users) - 1) // batch_size + 1}"
                )
                self._process_unfollow_batch(batch, workers, dry_run)
        else:
            self._process_unfollow_batch(users, workers, dry_run)

        logger.info(
            f"✅ Batch unfollow completed: {self.metrics.unfollowed} successful, {self.metrics.failed_unfollows} failed"
        )

    def _process_unfollow_batch(self, users: List[Dict], workers: int, dry_run: bool):
        """Process a single batch of unfollow operations."""
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}

            for user in users:
                username = user["login"]
                if dry_run:
                    logger.info(f"🧪 Would unfollow: {username}")
                    self.metrics.unfollowed += 1
                else:
                    future = executor.submit(self.unfollow_user, username)
                    futures[future] = username

            # Wait for all operations to complete
            if not dry_run:
                for future in as_completed(futures):
                    username = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"❌ Executor error for {username}: {e}")
                        self.metrics.failed_unfollows += 1

    def apply_filters(self, users: List[Dict]) -> List[Dict]:
        """
        Apply configurable filters to the unfollow list.

        Args:
            users: List of user dicts to filter

        Returns:
            Filtered list of users
        """
        follow_config = self.config.FOLLOW_CONFIG
        filtered_users = []

        for user in users:
            username = user.get("login", "")

            # Check whitelist (never unfollow whitelisted users)
            if username in follow_config.get("whitelist", []):
                logger.debug(f"⏭️  Skipping whitelisted user: {username}")
                self.metrics.skipped_whitelist += 1
                continue

            # Check blacklist (always unfollow blacklisted users)
            if username in follow_config.get("blacklist", []):
                filtered_users.append(user)
                continue

            # For other users, apply normal filtering logic
            filtered_users.append(user)

        skipped = len(users) - len(filtered_users) - self.metrics.skipped_whitelist
        self.metrics.skipped_filters = skipped

        logger.info(
            f"🔧 Filters applied: {len(users)} total -> "
            f"{len(filtered_users)} to unfollow, "
            f"{self.metrics.skipped_whitelist} whitelisted, "
            f"{self.metrics.skipped_filters} filtered out"
        )
        return filtered_users

    def export_report(self, file_path: str) -> None:
        """
        Export a detailed report of the operation.

        Args:
            file_path: Path to output report file
        """
        import csv
        from datetime import datetime

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = [
                    "timestamp",
                    "total_following",
                    "total_followers",
                    "non_reciprocal",
                    "unfollowed",
                    "failed",
                    "skipped_whitelist",
                    "skipped_filters",
                    "duration_seconds",
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                writer.writerow(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "total_following": self.metrics.total_following,
                        "total_followers": self.metrics.total_followers,
                        "non_reciprocal": self.metrics.non_reciprocal,
                        "unfollowed": self.metrics.unfollowed,
                        "failed": self.metrics.failed_unfollows,
                        "skipped_whitelist": self.metrics.skipped_whitelist,
                        "skipped_filters": self.metrics.skipped_filters,
                        "duration_seconds": round(self.metrics.elapsed_time, 2),
                    }
                )

            logger.info(f"💾 Report exported to {file_path}")

        except Exception as e:
            logger.error(f"❌ Failed to export report: {e}")


@time_it
def main():
    """
    Main execution function for automated follow diff cleanup.
    Designed to run in CI/CD without user interaction.
    """
    logger.info("🚀 Starting Automated GitHub Follow Cleanup")
    logger.info(f"🔧 Mode: {'DRY RUN' if config.DRY_RUN else 'LIVE'}")

    activity_service = GitHubActivityService()
    connector_service = GitHubConnectorService()

    analyzer = FollowDiffAnalyzer(activity_service, connector_service, config)

    try:
        # Load and analyze follow data
        analyzer.load_follow_data()
        non_reciprocal_users = analyzer.find_non_reciprocal_users()

        # Log analysis results
        logger.info("📊 Follow Analysis:")
        logger.info(f"   Users you follow: {analyzer.metrics.total_following}")
        logger.info(f"   Your followers: {analyzer.metrics.total_followers}")
        logger.info(f"   Non-reciprocal: {analyzer.metrics.non_reciprocal}")

        if not non_reciprocal_users:
            logger.info("✅ No non-reciprocal follows found. All good!")
            return

        # Apply filters from config
        users_to_unfollow = analyzer.apply_filters(non_reciprocal_users)

        if not users_to_unfollow:
            logger.info("✅ No users to unfollow after applying filters")
            return

        # Log what we're about to do
        logger.info(f"🎯 Preparing to unfollow {len(users_to_unfollow)} users")

        if config.DRY_RUN:
            logger.info("🧪 DRY RUN: Simulating unfollows...")
        else:
            logger.warning(
                f"⚠️  LIVE MODE: Will unfollow {len(users_to_unfollow)} users"
            )

        # Execute batch unfollow
        analyzer.batch_unfollow(users_to_unfollow, dry_run=config.DRY_RUN)

        # Export report
        report_file = config.OUTPUT_FILE.replace(".csv", "_diff_report.csv")
        analyzer.export_report(report_file)

        # Print summary
        logger.info(analyzer.metrics.summary())

        # Exit with appropriate code
        if analyzer.metrics.failed_unfollows > 0:
            logger.warning(
                f"⚠️  Completed with {analyzer.metrics.failed_unfollows} failures"
            )
            sys.exit(1)
        else:
            logger.info("✅ Cleanup completed successfully!")
            sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Process interrupted by user")
        sys.exit(130)
