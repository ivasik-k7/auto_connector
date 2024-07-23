from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

from app.services import OrganizationConnector
from app.utils import StorageManager, config, setup_logger

logger = setup_logger(__name__, log_file="org.log")


def process_follower(follower, connector_service, file_manager):
    username = follower.get("login")
    try:
        language = connector_service.get_follower_top_lang(username)
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


def main():
    load_dotenv()

    connector_service = OrganizationConnector()
    organizations = ["ivasik-k7"]

    with StorageManager("examples/profiles.txt") as file_manager:
        with ThreadPoolExecutor(config.MAX_WORKERS) as executor:
            futures = []

            for org in organizations:
                try:
                    followers = connector_service.receive_followers(org)
                    for follower in followers:
                        futures.append(
                            executor.submit(
                                process_follower,
                                follower,
                                connector_service,
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
