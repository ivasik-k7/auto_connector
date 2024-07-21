from dotenv import load_dotenv

from app.services import GitHubConnector
from app.utils import MultiThreadStorage

if __name__ == "__main__":
    load_dotenv()

    connector_service = GitHubConnector()
    fs = MultiThreadStorage("active_profiles.json")

    for profile in fs.query(lambda x: x.get("lang") in "JavaScript"):
        connector_service.follow(profile.get("login"), delay=1)
