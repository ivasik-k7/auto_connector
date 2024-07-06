# import argparse

from argparse import ArgumentParser

from dotenv import load_dotenv

from app.services import GitHubConnector, OrganizationConnector
from app.utils import setup_logger

if __name__ == "__main__":
    load_dotenv()

    logger = setup_logger(__name__)

    parser = ArgumentParser(description="Unsubscribe a user by username")

    parser.add_argument(
        "-u",
        "--username",
        type=str,
        help="Username of the user",
    )

    parser.add_argument(
        "-uns",
        "--unsubscribe",
        action="store_true",
        default=False,
        help="Unsubscribe from not followed profiles",
    )

    args = parser.parse_args()

    s1 = OrganizationConnector()
    s2 = GitHubConnector()

    followers = s1.receive_followers(args.username)
    followings = s1.receive_following(args.username)

    count = 0

    for profile in followings:
        if profile not in followers:
            username = profile.get("login")
            logger.debug(f"Not subscribed to you: {username}")
            count += 1
            if args.unsubscribe:
                s2.unfollow(username)

    logger.debug(f"Total unsub diff {count}")
