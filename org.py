import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

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

logger = setup_logger(__name__, log_file="org.log")


def process_follower(follower, stats_service, file_manager):
    username = follower.get("login")
    try:
        language = stats_service.get_top_language(username)
        file_manager.add(
            {
                "id": follower.get("id", ""),
                "login": username,
                "lang": str(language),
                "rank": None,
                "url": follower.get("html_url"),
            }
        )
    except Exception as e:
        logger.error(f"Error processing follower {username}: {e}")


@time_it
def main():
    activity_service = GitHubActivityService()
    stats_service = GitHubStatsService()
    connector = GitHubConnectorService()

    organizations = ["MdShawonForazi"]
    with StorageManager("examples/profiles.csv") as file_manager:
        with ThreadPoolExecutor(config.MAX_WORKERS) as executor:
            futures = []

            for org in organizations:
                try:
                    logger.info(f"📊 Fetching followers for organization: {org}")
                    followers = activity_service.get_followers(org)
                    logger.info(f"✅ Found {len(followers)} followers for {org}")

                    for follower in followers:
                        connector.follow(follower.get("login"))

                        futures.append(
                            executor.submit(
                                process_follower,
                                follower,
                                stats_service,
                                file_manager,
                            )
                        )
                except Exception as e:
                    logger.error(
                        f"Error receiving followers for organization {org}: {e}"
                    )

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing future: {e}")


if __name__ == "__main__":
    main()
