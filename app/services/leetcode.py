import requests
from bs4 import BeautifulSoup


class LeetcodeSpectator:
    def get_statistics(self, username):
        url = f"https://leetcode.com/u/{username}/"
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            stats = {}

            profile_header = soup.find("div", class_="profile-header")
            if profile_header:
                stats["username"] = username
                stats["profile_pic"] = profile_header.find("img")["src"]

            return stats
        else:
            raise Exception(f"Failed to fetch data: {response.status_code}")
