import signal
import sys
from random import randint
from time import sleep

from app.services import GitHubConnectorService
from app.utils import MultiThreadStorage
from app.utils.config import Config


def signal_handler(sig, frame):
    print("Termination signal received. Cleaning up...")
    sys.exit(0)


def setup_environment():
    """Load and validate environment configuration."""
    print("🔧 Setting up environment...")

    try:
        config = Config.load(validate_with_github=True)
        print("✅ Environment setup completed successfully")
        return config
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("\nPlease make sure you have:")
        print("1. Created a .env file in your project root")
        print("2. Added your GITHUB_TOKEN to the .env file")
        print("3. The token has required permissions (user, write:user)")
        sys.exit(1)


def main():
    # Setup environment first
    setup_environment()

    try:
        svc = GitHubConnectorService()
        fs = MultiThreadStorage("examples/profiles.csv")

        profiles = fs.query(lambda x: x.get("lang") == "C")[::-1]
        print(f"📊 Found {len(profiles)} profiles to process")

        if not profiles:
            print("❌ No profiles found matching the criteria")
            return

        for i, profile in enumerate(profiles, 1):
            username = profile.get("login")
            if not username:
                continue

            print(f"👤 [{i}/{len(profiles)}] Processing: {username}")

            svc.follow(username)

            interval = randint(3, 10)
            print(f"⏳ Waiting {interval} seconds...")
            sleep(interval)

        print("✅ All profiles processed successfully!")

    except KeyboardInterrupt:
        print("\n⏹️  Operation interrupted by user")
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    main()
