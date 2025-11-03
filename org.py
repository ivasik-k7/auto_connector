import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional

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


def get_user_info_safe(stats_service, username: str) -> Dict[str, Any]:
    """
    Safely retrieve user information with fail-safe defaults.

    Args:
        stats_service: GitHub stats service instance
        username: GitHub username

    Returns:
        Dictionary with user information, using defaults if API calls fail
    """
    user_info = {
        "username": username,
        "language": "Unknown",
        "bio": None,
        "company": None,
        "location": None,
        "public_repos": 0,
        "followers": 0,
        "following": 0,
        "created_at": None,
    }

    try:
        # Get top language
        language = stats_service.get_top_language(username)
        user_info["language"] = str(language) if language else "Unknown"
    except Exception as e:
        logger.warning(f"Could not fetch language for {username}: {e}")

    try:
        # Try to get additional user details if available
        # Assuming stats_service has a method to get user details
        user_details = stats_service.get_user_details(username)
        if user_details:
            user_info.update(
                {
                    "bio": user_details.get("bio"),
                    "company": user_details.get("company"),
                    "location": user_details.get("location"),
                    "public_repos": user_details.get("public_repos", 0),
                    "followers": user_details.get("followers", 0),
                    "following": user_details.get("following", 0),
                    "created_at": user_details.get("created_at"),
                }
            )
    except AttributeError:
        logger.debug(f"get_user_details not available for {username}")
    except Exception as e:
        logger.warning(f"Could not fetch details for {username}: {e}")

    return user_info


def process_follower(
    follower: Dict[str, Any], stats_service, file_manager, should_follow: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Process a single follower with enhanced error handling.

    Args:
        follower: Follower data from GitHub API
        stats_service: GitHub stats service instance
        file_manager: Storage manager for saving data
        should_follow: Whether to follow this user back

    Returns:
        Processed follower data or None if processing failed
    """
    username = follower.get("login")
    if not username:
        logger.error("Follower missing 'login' field")
        return None

    try:
        user_info = get_user_info_safe(stats_service, username)

        follower_data = {
            "id": follower.get("id", ""),
            "login": username,
            "lang": user_info["language"],
            "bio": user_info.get("bio", "")[:200]
            if user_info.get("bio")
            else "",  # Truncate long bios
            "company": user_info.get("company", ""),
            "location": user_info.get("location", ""),
            "public_repos": user_info.get("public_repos", 0),
            "followers": user_info.get("followers", 0),
            "following": user_info.get("following", 0),
            "rank": None,
            "url": follower.get("html_url", f"https://github.com/{username}"),
            "followed_back": should_follow,
        }

        file_manager.add(follower_data)
        logger.info(f"✅ Successfully processed: {username}")
        return follower_data

    except Exception as e:
        logger.error(f"❌ Error processing follower {username}: {e}", exc_info=True)
        return None


def should_follow_user(
    username: str, user_info: Dict[str, Any], config_filters: Dict[str, Any]
) -> bool:
    """
    Determine if a user should be followed based on configuration filters.

    Args:
        username: GitHub username
        user_info: User information dictionary
        config_filters: Configuration filters for following users

    Returns:
        Boolean indicating whether to follow the user
    """
    # Check if user is in whitelist
    if config_filters.get("whitelist"):
        return username in config_filters["whitelist"]

    # Check if user is in blacklist
    if config_filters.get("blacklist") and username in config_filters["blacklist"]:
        return False

    # Check language filter
    if config_filters.get("languages"):
        if user_info.get("language", "Unknown") not in config_filters["languages"]:
            return False

    # Check minimum repos
    min_repos = config_filters.get("min_repos", 0)
    if user_info.get("public_repos", 0) < min_repos:
        return False

    # Check minimum followers
    min_followers = config_filters.get("min_followers", 0)
    if user_info.get("followers", 0) < min_followers:
        return False

    return True


@time_it
def main():
    """
    Main function to sync followers from specified organizations.

    Configuration example (add to your config file or environment):
    FOLLOW_CONFIG = {
        "enabled": True,  # Master switch for following
        "whitelist": ["user1", "user2"],  # If set, only follow these users
        "blacklist": ["spammer1"],  # Never follow these users
        "languages": ["Python", "JavaScript"],  # Only follow users with these languages
        "min_repos": 5,  # Minimum number of public repositories
        "min_followers": 10,  # Minimum number of followers
    }
    """
    activity_service = GitHubActivityService()
    stats_service = GitHubStatsService()
    connector = GitHubConnectorService()

    # Configuration for which followers to follow back
    follow_config = getattr(
        config,
        "FOLLOW_CONFIG",
        {
            "enabled": False,  # Default: don't auto-follow
            "whitelist": None,
            "blacklist": [],
            "languages": None,
            "min_repos": 0,
            "min_followers": 0,
        },
    )

    organizations = getattr(config, "TARGET_ORGANIZATIONS", ["ivasik-k7"])

    logger.info(f"🚀 Starting follower sync for organizations: {organizations}")
    logger.info(f"⚙️  Follow-back enabled: {follow_config.get('enabled', False)}")

    with StorageManager("examples/profiles.csv") as file_manager:
        with ThreadPoolExecutor(config.MAX_WORKERS) as executor:
            futures = []
            total_followers = 0

            for org in organizations:
                try:
                    logger.info(f"📊 Fetching followers for organization: {org}")
                    followers = activity_service.get_followers(org)
                    follower_count = len(followers)
                    total_followers += follower_count
                    logger.info(f"✅ Found {follower_count} followers for {org}")

                    for follower in reversed(followers):
                        username = follower.get("login")
                        if not username:
                            continue

                        user_info = get_user_info_safe(stats_service, username)
                        should_follow = follow_config.get(
                            "enabled", False
                        ) and should_follow_user(username, user_info, follow_config)

                        if should_follow:
                            try:
                                connector.follow(username)
                                logger.info(f"👥 Followed: {username}")
                            except Exception as e:
                                logger.error(f"Failed to follow {username}: {e}")

                        # Submit processing task
                        futures.append(
                            executor.submit(
                                process_follower,
                                follower,
                                stats_service,
                                file_manager,
                                should_follow,
                            )
                        )

                except Exception as e:
                    logger.error(
                        f"❌ Error receiving followers for organization {org}: {e}",
                        exc_info=True,
                    )

            # Wait for all processing to complete
            successful = 0
            failed = 0
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        successful += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"❌ Error processing future: {e}", exc_info=True)
                    failed += 1

            logger.info(f"\n{'=' * 60}")
            logger.info("📈 Summary:")
            logger.info(f"   Total followers found: {total_followers}")
            logger.info(f"   Successfully processed: {successful}")
            logger.info(f"   Failed: {failed}")
            logger.info(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
