"""
Enhanced Configuration System with Validation and Dynamic Loading
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Enhanced configuration with comprehensive settings."""

    # GitHub API Settings
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_API_URL: str = os.getenv("GITHUB_API_URL", "https://api.github.com")

    # Logging Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "github_logs.log")
    LOG_FORMAT: str = os.getenv(
        "LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Performance Settings
    RETRY_ATTEMPTS: int = int(os.getenv("RETRY_ATTEMPTS", "3"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "10"))
    RATE_LIMIT_BUFFER: int = int(os.getenv("RATE_LIMIT_BUFFER", "100"))

    # Processing Settings
    PROCESSING_STRATEGY: str = os.getenv("PROCESSING_STRATEGY", "balanced")
    TARGET_ORGANIZATIONS: List[str] = field(
        default_factory=lambda: json.loads(
            os.getenv("TARGET_ORGANIZATIONS", '["ivasik-k7"]')
        )
    )
    OUTPUT_FILE: str = os.getenv("OUTPUT_FILE", "out/profiles.csv")
    ENABLE_CACHING: bool = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour

    FOLLOW_CONFIG: Dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": os.getenv("FOLLOW_ENABLED", "false").lower() == "true",
            "whitelist": json.loads(os.getenv("FOLLOW_WHITELIST", "[]")),
            "blacklist": json.loads(os.getenv("FOLLOW_BLACKLIST", "[]")),
            "languages": json.loads(os.getenv("FOLLOW_LANGUAGES", "[]")) or None,
            "min_repos": int(os.getenv("FOLLOW_MIN_REPOS", "0")),
            "max_repos": int(os.getenv("FOLLOW_MAX_REPOS", "999999")),
            "min_followers": int(os.getenv("FOLLOW_MIN_FOLLOWERS", "0")),
            "max_followers": int(os.getenv("FOLLOW_MAX_FOLLOWERS", "999999")),
            "min_following": int(os.getenv("FOLLOW_MIN_FOLLOWING", "0")),
            "required_keywords": json.loads(
                os.getenv("FOLLOW_REQUIRED_KEYWORDS", "[]")
            ),
            "exclude_keywords": json.loads(os.getenv("FOLLOW_EXCLUDE_KEYWORDS", "[]")),
            "min_account_age_days": int(os.getenv("FOLLOW_MIN_ACCOUNT_AGE_DAYS", "0")),
            "delay_between_follows": float(os.getenv("FOLLOW_DELAY", "1.0")),
        }
    )

    # Advanced Features
    ENABLE_EMAIL_EXTRACTION: bool = (
        os.getenv("ENABLE_EMAIL_EXTRACTION", "false").lower() == "true"
    )
    ENABLE_SOCIAL_LINKS: bool = (
        os.getenv("ENABLE_SOCIAL_LINKS", "true").lower() == "true"
    )
    ENABLE_LANGUAGE_STATS: bool = (
        os.getenv("ENABLE_LANGUAGE_STATS", "false").lower() == "true"
    )
    ENABLE_CONTRIBUTION_STATS: bool = (
        os.getenv("ENABLE_CONTRIBUTION_STATS", "false").lower() == "true"
    )

    # Batch Processing
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "100"))
    PROCESS_IN_BATCHES: bool = (
        os.getenv("PROCESS_IN_BATCHES", "false").lower() == "true"
    )

    # Safety Settings
    DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() == "true"
    MAX_FOLLOWS_PER_RUN: int = int(os.getenv("MAX_FOLLOWS_PER_RUN", "100"))
    STOP_ON_ERROR_THRESHOLD: int = int(os.getenv("STOP_ON_ERROR_THRESHOLD", "10"))

    def validate(self) -> bool:
        """Validate basic configuration."""
        errors = []

        if not self.GITHUB_TOKEN:
            errors.append("GITHUB_TOKEN environment variable is required")

        if not self.GITHUB_TOKEN.startswith(("ghp_", "github_pat_", "gho_", "ghu_")):
            print(
                "⚠️  Warning: GITHUB_TOKEN doesn't look like a valid GitHub token format"
            )

        if self.MAX_WORKERS < 1:
            errors.append("MAX_WORKERS must be at least 1")

        if self.MAX_WORKERS > 50:
            print("⚠️  Warning: MAX_WORKERS > 50 may cause rate limiting issues")

        if self.REQUEST_TIMEOUT < 5:
            errors.append("REQUEST_TIMEOUT must be at least 5 seconds")

        valid_strategies = ["fast", "balanced", "comprehensive", "custom"]
        if self.PROCESSING_STRATEGY not in valid_strategies:
            errors.append(f"PROCESSING_STRATEGY must be one of: {valid_strategies}")

        if self.FOLLOW_CONFIG["enabled"]:
            if self.FOLLOW_CONFIG["min_repos"] > self.FOLLOW_CONFIG["max_repos"]:
                errors.append(
                    "FOLLOW_MIN_REPOS cannot be greater than FOLLOW_MAX_REPOS"
                )

            if (
                self.FOLLOW_CONFIG["min_followers"]
                > self.FOLLOW_CONFIG["max_followers"]
            ):
                errors.append(
                    "FOLLOW_MIN_FOLLOWERS cannot be greater than FOLLOW_MAX_FOLLOWERS"
                )

        output_dir = os.path.dirname(self.OUTPUT_FILE)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create output directory: {e}")

        if errors:
            for error in errors:
                print(f"❌ {error}")
            raise ValueError("Configuration validation failed")

        return True

    def validate_with_github(self) -> bool:
        """Validate GitHub token and check permissions."""
        headers = {
            "Authorization": f"token {self.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

        try:
            response = requests.get(
                f"{self.GITHUB_API_URL}/user",
                headers=headers,
                timeout=self.REQUEST_TIMEOUT,
            )

            if response.status_code == 200:
                user_data = response.json()
                print(f"✅ GitHub token validated!")
                print(f"   Authenticated as: {user_data['login']}")
                print(f"   Account type: {user_data.get('type', 'Unknown')}")

                rate_limit_response = requests.get(
                    f"{self.GITHUB_API_URL}/rate_limit", headers=headers, timeout=10
                )

                if rate_limit_response.status_code == 200:
                    rate_data = rate_limit_response.json()
                    core_limit = rate_data.get("resources", {}).get("core", {})
                    remaining = core_limit.get("remaining", 0)
                    limit = core_limit.get("limit", 0)

                    print(f"   Rate limit: {remaining}/{limit} requests remaining")

                    if remaining < 100:
                        print("⚠️  Warning: Low rate limit remaining!")

                scopes = response.headers.get("X-OAuth-Scopes", "")
                print(f"   Token scopes: {scopes or 'None'}")

                required_scopes = {"user"}
                if self.FOLLOW_CONFIG.get("enabled"):
                    required_scopes.add("user:follow")

                missing_scopes = required_scopes - set(
                    s.strip() for s in scopes.split(",")
                )

                if missing_scopes:
                    print(f"⚠️  Warning: Missing recommended scopes: {missing_scopes}")
                    print("   Some features may not work correctly")

                return True

            elif response.status_code == 401:
                print("❌ Token validation failed: Invalid credentials")
                print("   Your token may be expired or invalid")
                return False

            elif response.status_code == 403:
                print("❌ Token validation failed: Forbidden")
                print("   Your token may not have sufficient permissions")
                return False

            else:
                print(f"❌ Token validation failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False

        except requests.exceptions.Timeout:
            print("❌ Token validation failed: Request timeout")
            print("   Check your network connection")
            return False

        except requests.exceptions.ConnectionError:
            print("❌ Token validation failed: Connection error")
            print("   Cannot reach GitHub API")
            return False

        except requests.exceptions.RequestException as e:
            print(f"❌ Error validating token: {e}")
            return False

    def print_configuration(self):
        """Print current configuration for review."""
        print("\n" + "=" * 70)
        print("📋 Configuration Summary")
        print("=" * 70)
        print(f"Processing Strategy:    {self.PROCESSING_STRATEGY}")
        print(f"Target Organizations:   {', '.join(self.TARGET_ORGANIZATIONS)}")
        print(f"Max Workers:            {self.MAX_WORKERS}")
        print(f"Output File:            {self.OUTPUT_FILE}")
        print(f"Dry Run Mode:           {self.DRY_RUN}")
        print(f"\nFollow Settings:")
        print(f"  Enabled:              {self.FOLLOW_CONFIG['enabled']}")
        if self.FOLLOW_CONFIG["enabled"]:
            print(f"  Min Repos:            {self.FOLLOW_CONFIG['min_repos']}")
            print(f"  Min Followers:        {self.FOLLOW_CONFIG['min_followers']}")
            print(
                f"  Languages Filter:     {self.FOLLOW_CONFIG['languages'] or 'None'}"
            )
            print(f"  Max Follows/Run:      {self.MAX_FOLLOWS_PER_RUN}")
        print(f"\nAdvanced Features:")
        print(f"  Caching:              {self.ENABLE_CACHING}")
        print(f"  Email Extraction:     {self.ENABLE_EMAIL_EXTRACTION}")
        print(f"  Social Links:         {self.ENABLE_SOCIAL_LINKS}")
        print(f"  Language Stats:       {self.ENABLE_LANGUAGE_STATS}")
        print(f"  Contribution Stats:   {self.ENABLE_CONTRIBUTION_STATS}")
        print("=" * 70 + "\n")

    @classmethod
    def load(cls, validate_with_github: bool = True) -> "Config":
        """
        Load and validate configuration.

        Args:
            validate_with_github: Whether to validate token with GitHub API

        Returns:
            Validated Config instance
        """
        config = cls()

        try:
            config.validate()
        except ValueError as e:
            print(f"\n❌ Configuration validation failed: {e}")
            sys.exit(1)

        if validate_with_github:
            if not config.validate_with_github():
                print("\n💡 How to fix:")
                print("1. Go to: https://github.com/settings/tokens")
                print("2. Generate a new token (classic) with these scopes:")
                print("   - 'user' (required)")
                print("   - 'user:follow' (required for auto-follow)")
                print("   - 'read:org' (optional, for organization data)")
                print("3. Update your .env file:")
                print("   GITHUB_TOKEN=your_new_token_here")
                print("4. Restart the application")
                sys.exit(1)

        config.print_configuration()

        return config

    @classmethod
    def from_file(cls, config_file: str) -> "Config":
        """
        Load configuration from a JSON file.

        Args:
            config_file: Path to JSON configuration file

        Returns:
            Config instance
        """
        try:
            with open(config_file, "r") as f:
                config_data = json.load(f)

            for key, value in config_data.items():
                if hasattr(cls, key):
                    os.environ[key] = (
                        json.dumps(value)
                        if isinstance(value, (dict, list))
                        else str(value)
                    )

            return cls.load(validate_with_github=False)

        except FileNotFoundError:
            print(f"❌ Configuration file not found: {config_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in configuration file: {e}")
            sys.exit(1)

    def to_file(self, config_file: str):
        """Save configuration to a JSON file."""
        config_dict = {
            "GITHUB_API_URL": self.GITHUB_API_URL,
            "LOG_LEVEL": self.LOG_LEVEL,
            "MAX_WORKERS": self.MAX_WORKERS,
            "PROCESSING_STRATEGY": self.PROCESSING_STRATEGY,
            "TARGET_ORGANIZATIONS": self.TARGET_ORGANIZATIONS,
            "OUTPUT_FILE": self.OUTPUT_FILE,
            "FOLLOW_CONFIG": self.FOLLOW_CONFIG,
        }

        with open(config_file, "w") as f:
            json.dump(config_dict, f, indent=2)

        print(f"✅ Configuration saved to: {config_file}")
