import signal
import sys

from dotenv import load_dotenv

from app.services import GitHubConnector
from app.utils import MultiThreadStorage


def signal_handler(sig, frame):
    print("Termination signal received. Cleaning up...")
    sys.exit(0)


def main():
    load_dotenv()

    try:
        connector_service = GitHubConnector()
        fs = MultiThreadStorage("examples/profiles.xml")

        for profile in fs.query(lambda x: x.get("lang") == "Python"):
            connector_service.follow(profile.get("login"), delay=4)

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    main()
