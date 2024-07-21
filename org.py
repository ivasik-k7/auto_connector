from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

from app.services import OrganizationConnector
from app.utils import StorageManager, setup_logger

logger = setup_logger(__name__, log_file="org.log")


def process_follower(follower, connector_service, fm):
    username = follower.get("login")
    language = connector_service.get_follower_top_lang(username)
    if language:
        logger.info(f"{username} with {language} added!")
        fm.add(
            {
                "id": follower.get("id", ""),
                "login": username,
                "lang": language,
                "avatar": follower.get("avatar_url", ""),
                "type": follower.get("type", "User"),
                "url": follower.get("html_url"),
            }
        )


if __name__ == "__main__":
    load_dotenv()
    organizations = ["ivasik-k7"]
    connector_service = OrganizationConnector()

    with StorageManager("examples/profiles.json") as fm:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for org in organizations:
                followers = connector_service.receive_followers(org)
                for follower in followers:
                    futures.append(
                        executor.submit(
                            process_follower,
                            follower,
                            connector_service,
                            fm,
                        )
                    )

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing follower: {e}")

            fm.save_as_csv("examples/profiles.csv")
