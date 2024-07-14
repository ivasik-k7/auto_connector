from dotenv import load_dotenv

from app.services import OrganizationConnector
from app.utils import FileStorage, setup_logger

logger = setup_logger(__name__, log_file="org.log")

if __name__ == "__main__":
    load_dotenv()

    s2 = OrganizationConnector()
    fs = FileStorage("organizations.json")

    organizations = []

    for org in organizations:
        resp = s2.receive_followers(org)

        for info in resp:
            username = info.get("login")
            lang = s2.get_follower_top_lang(username)
            if lang:
                logger.info(f"{username} with {lang} added!")
                fs.add(
                    key=username,
                    content={
                        "id": info.get("id"),
                        "avatar": info.get("avatar_url", ""),
                        "type": info.get("type", "User"),
                        "url": info.get("html_url"),
                        "lang": lang,
                    },
                )
