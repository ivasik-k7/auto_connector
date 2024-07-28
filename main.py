import signal
import sys
from random import randint
from time import sleep

from dotenv import load_dotenv

from app.services import GitHubConnectorService
from app.utils import MultiThreadStorage


def signal_handler(sig, frame):
    print("Termination signal received. Cleaning up...")
    sys.exit(0)


def main():
    load_dotenv()

    try:
        svc = GitHubConnectorService()
        fs = MultiThreadStorage("examples/profiles.csv")

        for profile in fs.query(lambda x: x.get("lang") == "C")[::-1]:
            interval = randint(1, 7)
            username = profile.get("login")
            svc.follow(username)
            interval = randint(1, 7)

            sleep(interval)

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    main()
