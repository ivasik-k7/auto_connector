"""
GitHub Follow Diff - Find and unfollow users who don't follow you back
"""

import argparse
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

logger = setup_logger(__name__, log_file="follow_diff.log")


@dataclass
class DiffMetrics:
    """Metrics for tracking diff operations."""

    total_following: int = 0
    total_followers: int = 0
    non_reciprocal: int = 0
    unfollowed: int = 0
    failed_unfollows: int = 0
    start_time: float = field(default_factory=time.time)

    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time

    def summary(self) -> str:
        return (
            f"\n{'=' * 70}\n"
            f"📊 Follow Diff Summary:\n"
            f"{'=' * 70}\n"
            f"  Total Following:      {self.total_following}\n"
            f"  Total Followers:      {self.total_followers}\n"
            f"  Non-reciprocal:       {self.non_reciprocal}\n"
            f"  Successfully Unfollowed: {self.unfollowed}\n"
            f"  Failed Unfollows:     {self.failed_unfollows}\n"
            f"  Duration:             {self.elapsed_time:.2f}s\n"
            f"  Reciprocal Rate:      {(self.total_following - self.non_reciprocal) / self.total_following * 100:.1f}%\n"
            f"{'=' * 70}\n"
        )


class FollowDiffAnalyzer:
    """
    Analyzes follow relationships and manages unfollow operations.
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
            if hasattr(self.config, "FOLLOW_CONFIG") and self.config.FOLLOW_CONFIG.get(
                "delay_between_follows"
            ):
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
        max_workers: Optional[int] = None,
        dry_run: bool = False,
    ) -> None:
        """
        Unfollow multiple users concurrently.

        Args:
            users: List of user dicts to unfollow
            max_workers: Maximum concurrent workers
            dry_run: If True, only simulate without actual unfollowing
        """
        if not users:
            logger.info("✅ No users to unfollow")
            return

        if dry_run:
            logger.info("🧪 DRY RUN MODE - No actual unfollows will be performed")

        # Use config values with fallbacks
        workers = max_workers or getattr(self.config, "MAX_WORKERS", 5)
        batch_size = getattr(self.config, "BATCH_SIZE", 50)

        # Apply safety limits from config
        max_unfollows = getattr(self.config, "MAX_FOLLOWS_PER_RUN", 100)
        if len(users) > max_unfollows:
            logger.warning(
                f"⚠️  Limiting unfollows to {max_unfollows} (config: MAX_FOLLOWS_PER_RUN)"
            )
            users = users[:max_unfollows]

        logger.info(
            f"🚀 Starting batch unfollow for {len(users)} users (workers: {workers})"
        )

        # Process in batches if configured
        if getattr(self.config, "PROCESS_IN_BATCHES", False):
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

    def analyze_reciprocity(self) -> Dict[str, any]:
        """
        Analyze follow reciprocity and return detailed statistics.

        Returns:
            Dictionary with analysis results
        """
        non_reciprocal = self.find_non_reciprocal_users()
        reciprocal_count = self.metrics.total_following - self.metrics.non_reciprocal

        return {
            "total_following": self.metrics.total_following,
            "total_followers": self.metrics.total_followers,
            "non_reciprocal_count": self.metrics.non_reciprocal,
            "reciprocal_count": reciprocal_count,
            "reciprocity_rate": (reciprocal_count / self.metrics.total_following * 100)
            if self.metrics.total_following > 0
            else 0,
            "non_reciprocal_users": non_reciprocal,
            "follow_ratio": self.metrics.total_followers / self.metrics.total_following
            if self.metrics.total_following > 0
            else 0,
        }

    def export_non_reciprocal_users(self, file_path: str) -> None:
        """
        Export non-reciprocal users to a CSV file.

        Args:
            file_path: Path to output CSV file
        """
        import csv

        non_reciprocal = self.find_non_reciprocal_users()

        if not non_reciprocal:
            logger.info("No non-reciprocal users to export")
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = ["login", "id", "html_url", "type"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for user in non_reciprocal:
                    writer.writerow(
                        {
                            "login": user.get("login", ""),
                            "id": user.get("id", ""),
                            "html_url": user.get("html_url", ""),
                            "type": user.get("type", ""),
                        }
                    )

            logger.info(
                f"💾 Exported {len(non_reciprocal)} non-reciprocal users to {file_path}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to export users: {e}")

    def apply_filters(self, users: List[Dict]) -> List[Dict]:
        """
        Apply configurable filters to the unfollow list.

        Args:
            users: List of user dicts to filter

        Returns:
            Filtered list of users
        """
        if not hasattr(self.config, "FOLLOW_CONFIG"):
            return users

        follow_config = self.config.FOLLOW_CONFIG
        filtered_users = []

        for user in users:
            username = user.get("login", "")

            # Check whitelist (never unfollow whitelisted users)
            if username in follow_config.get("whitelist", []):
                logger.debug(f"⏭️  Skipping whitelisted user: {username}")
                continue

            # Check blacklist (always unfollow blacklisted users)
            if username in follow_config.get("blacklist", []):
                filtered_users.append(user)
                continue

            # For other users, apply normal filtering logic
            # (You could add more sophisticated filtering here based on user data)
            filtered_users.append(user)

        logger.info(f"🔧 Filters applied: {len(users)} -> {len(filtered_users)} users")
        return filtered_users


@time_it
def main():
    """
    Main execution function for follow diff analysis.
    """
    parser = argparse.ArgumentParser(
        description="Find and unfollow users who don't follow you back"
    )
    parser.add_argument(
        "--export", type=str, help="Export non-reciprocal users to CSV file"
    )
    parser.add_argument(
        "--unfollow-all", action="store_true", help="Unfollow all non-reciprocal users"
    )
    parser.add_argument("--max-workers", type=int, help="Maximum concurrent workers")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode for selective unfollowing",
    )
    parser.add_argument(
        "--apply-filters", action="store_true", help="Apply FOLLOW_CONFIG filters"
    )

    args = parser.parse_args()

    dry_run = args.dry_run or getattr(config, "DRY_RUN", False)

    activity_service = GitHubActivityService()
    connector_service = GitHubConnectorService()

    logger.info("🚀 Starting GitHub Follow Diff Analysis")

    analyzer = FollowDiffAnalyzer(activity_service, connector_service, config)

    try:
        analysis = analyzer.analyze_reciprocity()

        logger.info("📊 Follow Analysis:")
        logger.info(f"   Users you follow: {analysis['total_following']}")
        logger.info(f"   Your followers: {analysis['total_followers']}")
        logger.info(f"   Reciprocal follows: {analysis['reciprocal_count']}")
        logger.info(f"   Non-reciprocal follows: {analysis['non_reciprocal_count']}")
        logger.info(f"   Reciprocity rate: {analysis['reciprocity_rate']:.1f}%")
        logger.info(f"   Follow ratio: {analysis['follow_ratio']:.2f}")

        if args.export:
            analyzer.export_non_reciprocal_users(args.export)

        users_to_process = analysis["non_reciprocal_users"]
        if args.apply_filters:
            users_to_process = analyzer.apply_filters(users_to_process)
            logger.info(f"🔧 After filtering: {len(users_to_process)} users to process")

        if args.unfollow_all:
            if users_to_process:
                logger.warning(f"⚠️  About to unfollow {len(users_to_process)} users!")

                if not dry_run:
                    confirm = input("Type 'YES' to confirm: ")
                    if confirm != "YES":
                        logger.info("❌ Unfollow cancelled")
                        return

                analyzer.batch_unfollow(
                    users_to_process, max_workers=args.max_workers, dry_run=dry_run
                )
            else:
                logger.info("✅ No users to unfollow")

        elif args.interactive and users_to_process:
            logger.info("💬 Interactive mode - reviewing non-reciprocal users:")

            for i, user in enumerate(users_to_process, 1):
                print(f"\n[{i}/{len(users_to_process)}] {user['login']}")
                print(f"   Profile: {user.get('html_url', 'N/A')}")

                action = (
                    input("   Action: (s)kip, (u)nfollow, (q)uit: ").lower().strip()
                )

                if action == "q":
                    logger.info("👋 Exiting interactive mode")
                    break
                elif action == "u":
                    if dry_run:
                        logger.info(f"🧪 Would unfollow: {user['login']}")
                    else:
                        analyzer.unfollow_user(user["login"])
                else:
                    logger.info(f"⏭️  Skipped: {user['login']}")

        logger.info(analyzer.metrics.summary())

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Process interrupted by user")
        sys.exit(130)
