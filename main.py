from dotenv import load_dotenv

from app.services import GitHubConnector, OrganizationConnector
from app.utils import FS

if __name__ == "__main__":
    load_dotenv()

    s1 = OrganizationConnector()
    s2 = GitHubConnector()
    fs = FS("usernames.txt")

    organizations = []

    for org in organizations:
        resp = s1.receive_followers(org)

        for info in resp:
            fs.append(info.get("login"))

    profiles = fs.read().splitlines()

    for profile in profiles:
        s2.follow(profile)
