from abc import ABC, abstractmethod


class ConnectorService(ABC):
    @abstractmethod
    def follow(self, username: str):
        pass

    @abstractmethod
    def unfollow(self, username: str):
        pass


from app.services.github import GitHubConnector  # noqa
from app.services.github import OrganizationConnector  # noqa
from app.services.leetcode import LeetcodeSpectator  # noqa
