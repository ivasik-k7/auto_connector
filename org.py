from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

from app.services import GitHubActivityService, GitHubStatsService
from app.utils import StorageManager, config, setup_logger, time_it

logger = setup_logger(__name__, log_file="org.log")


@time_it
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
    load_dotenv()

    activity_service = GitHubActivityService()
    stats_service = GitHubStatsService()

    organizations = ["ivasik-k7"]

    with StorageManager("examples/profiles.xml") as file_manager:
        with ThreadPoolExecutor(config.MAX_WORKERS) as executor:
            futures = []

            for org in organizations:
                try:
                    followers = activity_service.get_followers(org)
                    for follower in followers:
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
