import requests

from app.services import ConnectorService
from app.utils import config


class GitHubConnector(ConnectorService):
    def __init__(self) -> None:
        self.base_url = "https://api.github.com"

    @property
    def headers(self):
        return {
            "Authorization": f"token {config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

    def follow(self, username: str):
        response = requests.put(
            f"{self.base_url}/user/following/{username}",
            headers=self.headers,
        )

        if response.status_code == 204:
            print(f"You are now following {username}.")
        else:
            print(f"Failed to follow {username}. Status code: {response.status_code}")
            print(response.text)

    def unfollow(self, username: str):
        response = requests.delete(
            f"{self.base_url}/user/following/{username}",
            headers=self.headers,
        )

        if response.status_code == 204:
            print(f"You have successfully unfollowed {username}.")
        else:
            print(f"Failed to unfollow {username}. Status code: {response.status_code}")
            print(response.text)


class OrganizationConnector:
    def __init__(self) -> None:
        self.base_url = "https://api.github.com"

    @property
    def headers(self):
        return {
            "Authorization": f"token {config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

    def receive_followers(self, username):
        response = requests.get(
            f"{self.base_url}/users/{username}/followers",
            headers=self.headers,
        )

        if response.status_code == 200:
            followers = response.json()
            return followers
        else:
            print(
                f"Failed to retrieve followers for {username}. Status code: {response.status_code}"
            )
            print(response.text)
            return None
