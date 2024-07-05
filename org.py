from dotenv import load_dotenv

from app.services import OrganizationConnector
from app.utils import FileStorage

if __name__ == "__main__":
    load_dotenv()

    s2 = OrganizationConnector()
    fs = FileStorage("profiles.json")

    organizations = []

    for org in organizations:
        resp = s2.receive_followers(org)

        for info in resp:
            lang = s2.get_follower_top_lang(info.get("login"))
            fs.add(
                key=info.get("login"),
                content={
                    "id": info.get("id"),
                    "avatar": info.get("avatar_url", ""),
                    "type": info.get("type", "User"),
                    "url": info.get("html_url"),
                    "lang": lang,
                },
            )
