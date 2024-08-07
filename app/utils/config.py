import os


class Config:
    @property
    def GITHUB_TOKEN(self):
        return os.environ.get("GITHUB_TOKEN", "token")

    @property
    def MAX_WORKERS(self):
        return 10
