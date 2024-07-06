from time import sleep

import requests

from app.services import ConnectorService
from app.utils import config, setup_logger

logger = setup_logger(__name__, log_file="github_logs.log")


class GitHubConnector(ConnectorService):
    def __init__(self) -> None:
        self.base_url = "https://api.github.com"

    @property
    def headers(self):
        return {
            "Authorization": f"token {config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

    def follow(self, username: str, delay: int | None):
        url = f"{self.base_url}/user/following/{username}"
        try:
            response = requests.put(url, headers=self.headers)

            response.raise_for_status()

            if response.status_code != 200:
                logger.debug(f"You has been already subscribed for {username}")
            else:
                logger.debug(f"You has been following to {username}")

            if delay:
                sleep(delay)
        except Exception as e:
            logger.exception(f"Following {username} exception: {str(e)}")

    def unfollow(self, username: str):
        url = f"{self.base_url}/user/following/{username}"
        try:
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            if response.status_code != 200:
                logger.debug(f"You has been already unsubscribed for {username}")
            else:
                logger.debug(f"You has been unfollowed {username}")
        except Exception as e:
            logger.exception(f"Unfollow {username} exception: {str(e)}")


class OrganizationConnector:
    def __init__(self) -> None:
        self.base_url = "https://api.github.com"

    @property
    def headers(self):
        return {
            "Authorization": f"token {config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

    def receive_followers(self, username: str):
        url = f"{self.base_url}/users/{username}/followers"
        page = 1
        per_page = 100
        followers = []
        try:
            while True:
                params = {"page": page, "per_page": per_page}
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()

                current_followers = response.json()
                if not current_followers:
                    break

                followers.extend(current_followers)
                page += 1

            return followers
        except requests.exceptions.RequestException as e:
            logger.exception(f"Error fetching followers for '{username}': {e}")
            return None

    def receive_following(self, username: str) -> list:
        url = f"{self.base_url}/users/{username}/following"
        page = 1
        per_page = 100
        followers = []
        try:
            while True:
                params = {"page": page, "per_page": per_page}
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()

                current_followers = response.json()
                if not current_followers:
                    break

                followers.extend(current_followers)
                page += 1

            return followers
        except requests.exceptions.RequestException as e:
            logger.exception(f"Error fetching followers for '{username}': {e}")
            return None

    def get_follower_top_lang(self, username: str) -> str:
        try:
            url = f"https://github-readme-stats.vercel.app/api/top-langs/?username={username}&theme=vue-dark&show_icons=true&hide_border=true&layout=compact&langs_count=1"
            response = requests.get(url)
            response.raise_for_status()

            lines = response.content.splitlines()

            for line in lines:
                decoded_line = line.decode("utf-8")

                index = decoded_line.find("100.00%")
                if index != -1:
                    left_content = decoded_line[:index].strip()
                    return left_content
        except Exception:
            return None
