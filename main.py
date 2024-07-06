from dotenv import load_dotenv

from app.services import GitHubConnector
from app.utils import FileStorage

if __name__ == "__main__":
    load_dotenv()

    s2 = GitHubConnector()
    fs = FileStorage("profiles.json")

    for profile in fs.data:
        username = profile.get("key")
        lang: str | None = profile.get("content").get("lang")
        if lang and "Java" in lang:
            s2.follow(username, delay=4)
