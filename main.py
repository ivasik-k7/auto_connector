from dotenv import load_dotenv

from app.services import GitHubConnector

if __name__ == "__main__":
    load_dotenv()

    svc = GitHubConnector()
    users = []

    for u in users:
        svc.follow(u)
