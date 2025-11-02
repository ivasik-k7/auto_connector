import os
import sys
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_API_URL: str = os.getenv("GITHUB_API_URL", "https://api.github.com")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "github_logs.log")

    RETRY_ATTEMPTS: int = int(os.getenv("RETRY_ATTEMPTS", "3"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "5"))

    def validate(self) -> bool:
        if not self.GITHUB_TOKEN:
            raise ValueError("GITHUB_TOKEN environment variable is required")

        if not self.GITHUB_TOKEN.startswith(("ghp_", "github_pat_", "gho_", "ghu_")):
            print(
                "⚠️  Warning: GITHUB_TOKEN doesn't look like a valid GitHub token format"
            )

        return True

    def validate_with_github(self) -> bool:
        headers = {
            "Authorization": f"token {self.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

        try:
            response = requests.get(
                f"{self.GITHUB_API_URL}/user", headers=headers, timeout=10
            )

            if response.status_code == 200:
                user_data = response.json()
                print(
                    f"✅ GitHub token validated! Authenticated as: {user_data['login']}"
                )

                scopes = response.headers.get("X-OAuth-Scopes", "")
                required_scopes = {"user", "write:user"}
                if not all(scope in scopes for scope in required_scopes):
                    print("⚠️  Warning: Token may be missing required scopes.")
                    print(f"   Current scopes: {scopes}")
                    print(f"   Required scopes: {', '.join(required_scopes)}")

                return True
            else:
                print(
                    f"❌ Token validation failed: {response.status_code} - {response.text}"
                )
                return False

        except requests.exceptions.RequestException as e:
            print(f"❌ Error validating token: {e}")
            return False

    @classmethod
    def load(cls, validate_with_github: bool = True) -> "Config":
        """Load and validate configuration."""
        config = cls()
        config.validate()

        if validate_with_github:
            if not config.validate_with_github():
                print("\n💡 How to fix:")
                print(
                    "1. Go to GitHub Settings → Developer settings → Personal access tokens"
                )
                print(
                    "2. Generate a new token with 'user' and 'write:user' permissions"
                )
                print("3. Update your .env file with: GITHUB_TOKEN=your_new_token_here")
                sys.exit(1)

        return config
