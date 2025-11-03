#!/usr/bin/env python3
"""
GitHub Candidate Finder Service
Finds random GitHub users with up to 20k followers from github-rank
"""

import json
import logging
import random
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class GitHubUser:
    """Data class to store GitHub user information"""

    rank: int
    name: str
    username: str
    followers: int
    followers_display: str
    location: str = ""
    company: str = ""


class GitHubCandidateService:
    """Service to find GitHub candidates with up to 20k followers"""

    def __init__(self, max_followers: int = 20000):
        self.base_url = "https://wangchujiang.com/github-rank/"
        self.max_followers = max_followers
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    def fetch_page_content(self) -> Optional[str]:
        """Fetch the GitHub rankings page content"""
        try:
            logger.info(f"Fetching GitHub rankings from {self.base_url}")
            response = self.session.get(self.base_url, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch page: {e}")
            return None

    def parse_users_from_html(self, html_content: str) -> List[GitHubUser]:
        """Parse users from HTML content using BeautifulSoup"""
        users = []
        soup = BeautifulSoup(html_content, "html.parser")

        # Find all table rows - skip the header row
        rows = soup.find_all("tr")
        logger.info(f"Found {len(rows)} total rows")

        for i, row in enumerate(rows):
            # Skip header rows by checking if it contains th elements
            if row.find("th"):
                continue

            user = self.parse_user_from_row(row)
            if user:
                users.append(user)

        logger.info(f"Successfully parsed {len(users)} users")
        return users

    def parse_user_from_row(self, row) -> Optional[GitHubUser]:
        """Parse a single user from a table row with flexible parsing"""
        try:
            cells = row.find_all("td")
            if len(cells) < 5:
                return None

            # Debug: log the structure of the first few rows to understand the format
            # if len(users) < 3:  # Only log first few for debugging
            #     logger.debug(
            #         f"Row cells: {[cell.get_text(strip=True) for cell in cells]}"
            #     )

            # Try multiple parsing strategies
            user_data = None

            # Strategy 1: Modern format with explicit data attributes
            user_data = self._parse_modern_format(cells)

            # Strategy 2: Traditional table format
            if not user_data:
                user_data = self._parse_traditional_format(cells)

            # Strategy 3: Flexible format matching
            if not user_data:
                user_data = self._parse_flexible_format(cells)

            if not user_data:
                return None

            rank, name, username, followers, followers_display, location, company = (
                user_data
            )

            return GitHubUser(
                rank=rank,
                name=name,
                username=username,
                followers=followers,
                followers_display=followers_display,
                location=location,
                company=company,
            )

        except Exception as e:
            logger.debug(f"Error parsing row: {str(e)}")
            return None

    def _parse_modern_format(self, cells) -> Optional[tuple]:
        """Parse modern format with user data in specific cells"""
        try:
            # Cell 0: Rank (usually contains the number)
            rank_text = cells[0].get_text(strip=True)
            rank_match = re.search(r"(\d+)", rank_text)
            if not rank_match:
                return None
            rank = int(rank_match.group(1))

            # Cell 1: User info (name, username, avatar)
            user_cell = cells[1]

            # Find username - look for span or direct text
            username_span = user_cell.find("span")
            username = username_span.get_text(strip=True) if username_span else ""

            # Find name - look for anchor tag or bold text
            name_link = user_cell.find("a", href=re.compile(r"github\.com"))
            if name_link:
                name_text = name_link.get_text(strip=True)
                # Remove rank number if present
                name = re.sub(r"^\d+\s*", "", name_text)
            else:
                # Try to find bold text for name
                bold_text = user_cell.find("b")
                name = bold_text.get_text(strip=True) if bold_text else username

            # Cell 2: Location
            location = cells[2].get_text(strip=True) if len(cells) > 2 else ""

            # Cell 3: Company
            company = cells[3].get_text(strip=True) if len(cells) > 3 else ""

            # Cell 4: Followers
            followers_cell = cells[4]
            followers_link = followers_cell.find("a")
            if followers_link:
                followers_text = followers_link.get_text(strip=True)
            else:
                followers_text = followers_cell.get_text(strip=True)

            followers, followers_display = self._parse_follower_count(followers_text)
            if followers is None:
                return None

            return (rank, name, username, followers, followers_text, location, company)

        except Exception as e:
            logger.debug(f"Modern format parsing failed: {e}")
            return None

    def _parse_traditional_format(self, cells) -> Optional[tuple]:
        """Parse traditional table format"""
        try:
            # Try to extract data by position with more flexible rules
            rank_text = cells[0].get_text(strip=True)
            rank_match = re.search(r"(\d+)", rank_text)
            if not rank_match:
                return None
            rank = int(rank_match.group(1))

            # Extract all text from user cell and parse name/username
            user_cell_text = cells[1].get_text(" ", strip=True)

            # Look for username pattern (usually lowercase, no spaces)
            username_match = re.search(
                r"\b([a-z0-9](?:[a-z0-9]|-(?=[a-z0-9])){0,38})\b", user_cell_text
            )
            username = username_match.group(1) if username_match else ""

            # Name is usually before username, clean it up
            if username:
                name_parts = user_cell_text.split(username)[0].strip()
                name = re.sub(r"^\d+\s*", "", name_parts).strip()
            else:
                name = user_cell_text

            # Location and company
            location = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            company = cells[3].get_text(strip=True) if len(cells) > 3 else ""

            # Followers
            followers_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            followers, followers_display = self._parse_follower_count(followers_text)
            if followers is None:
                return None

            return (rank, name, username, followers, followers_text, location, company)

        except Exception as e:
            logger.debug(f"Traditional format parsing failed: {e}")
            return None

    def _parse_flexible_format(self, cells) -> Optional[tuple]:
        """Most flexible parsing - extract data from any cell position"""
        try:
            # Find rank in any cell
            rank = None
            for cell in cells:
                rank_match = re.search(r"\b(\d+)\b", cell.get_text(strip=True))
                if rank_match and 1 <= int(rank_match.group(1)) <= 1000:
                    rank = int(rank_match.group(1))
                    break
            if not rank:
                return None

            # Find username (GitHub pattern)
            username = None
            for cell in cells:
                # Look for GitHub links
                github_links = cell.find_all(
                    "a", href=re.compile(r"github\.com/([^/]+)")
                )
                for link in github_links:
                    href = link.get("href", "")
                    user_match = re.search(r"github\.com/([^/?]+)", href)
                    if user_match:
                        username = user_match.group(1)
                        break
                if username:
                    break

            # Find name (usually near username)
            name = username or "Unknown"
            if username:
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    if username in cell_text:
                        # Extract name by removing username and cleaning
                        name_part = cell_text.replace(username, "").strip()
                        name_part = re.sub(r"^\d+\s*", "", name_part).strip()
                        if name_part and name_part != username:
                            name = name_part
                        break

            # Find followers (look for numbers with 'k' or large numbers)
            followers = None
            followers_text = ""
            for cell in cells:
                text = cell.get_text(strip=True)
                followers_match = re.search(r"(\d+\.?\d*)\s*k", text, re.IGNORECASE)
                if followers_match:
                    followers_text = followers_match.group(0)
                    followers = self._parse_follower_count(followers_text)[0]
                    break
                # Also check for large numbers that could be followers
                num_match = re.search(r"(\d{4,})", text)
                if num_match and 1000 <= int(num_match.group(1)) <= 500000:
                    followers = int(num_match.group(1))
                    followers_text = str(followers)
                    break

            if followers is None:
                return None

            # Location and company (try to identify by content)
            location = ""
            company = ""
            for cell in cells:
                text = cell.get_text(strip=True)
                if (
                    not text
                    or text == followers_text
                    or text == str(rank)
                    or text == username
                ):
                    continue
                # Simple heuristics for location and company
                if any(
                    indicator in text.lower()
                    for indicator in [",", "city", "country", "state", "us", "uk", "ca"]
                ):
                    location = text
                elif any(
                    indicator in text.lower()
                    for indicator in ["inc", "corp", "ltd", "llc", "@", "foundation"]
                ):
                    company = text

            return (rank, name, username, followers, followers_text, location, company)

        except Exception as e:
            logger.debug(f"Flexible format parsing failed: {e}")
            return None

    def _parse_follower_count(self, followers_text: str) -> tuple:
        """Parse follower count from text"""
        try:
            if not followers_text:
                return None, ""

            # Handle "13.831k" format
            k_match = re.search(r"([\d,]+\.?\d*)\s*k", followers_text, re.IGNORECASE)
            if k_match:
                num_str = k_match.group(1).replace(",", "")
                followers = int(float(num_str) * 1000)
                return followers, followers_text

            # Handle plain numbers
            num_match = re.search(r"([\d,]+)", followers_text)
            if num_match:
                followers = int(num_match.group(1).replace(",", ""))
                return followers, followers_text

            return None, followers_text
        except (ValueError, AttributeError):
            return None, followers_text

    def debug_html_structure(self, html_content: str, sample_rows: int = 3):
        """Debug method to understand the HTML structure"""
        soup = BeautifulSoup(html_content, "html.parser")
        rows = soup.find_all("tr")

        logger.info("=== HTML STRUCTURE DEBUG ===")
        for i, row in enumerate(rows[:sample_rows]):
            logger.info(f"Row {i}:")
            cells = row.find_all(["td", "th"])
            for j, cell in enumerate(cells):
                text = cell.get_text(strip=True)
                links = cell.find_all("a")
                link_hrefs = [link.get("href", "") for link in links]
                logger.info(f"  Cell {j}: '{text}' | Links: {link_hrefs}")
            logger.info("  ---")

    def find_candidates(self, limit: int = 50) -> List[GitHubUser]:
        """Find candidates with up to max_followers"""
        html_content = self.fetch_page_content()
        if not html_content:
            logger.warning("Using fallback data")
            return self.get_fallback_candidates()

        all_users = self.parse_users_from_html(html_content)

        # Filter users by follower count
        candidates = [
            user for user in all_users if user.followers <= self.max_followers
        ]

        # Limit the number of candidates
        return candidates[:limit]

    def get_random_candidate(self) -> Optional[GitHubUser]:
        """Get a random candidate from the filtered list"""
        candidates = self.find_candidates()

        if not candidates:
            logger.warning("No candidates found, using fallback")
            fallback_candidates = self.get_fallback_candidates()
            return random.choice(fallback_candidates) if fallback_candidates else None

        return random.choice(candidates)

    def get_fallback_candidates(self) -> List[GitHubUser]:
        """Provide fallback candidates when parsing fails"""
        return [
            GitHubUser(101, "Loiane Groner", "loiane", 19303, "19.303k", "Florida, US"),
            GitHubUser(104, "Chris Banes", "chrisbanes", 18826, "18.826k", "Bath, UK"),
            GitHubUser(
                105, "Jake Vanderplas", "jakevdp", 18760, "18.76k", "Oakland CA"
            ),
            GitHubUser(
                111, "Sandhika Galih", "sandhikagalih", 17824, "17.824k", "Indonesia"
            ),
            GitHubUser(
                112, "François Chollet", "fchollet", 17615, "17.615k", "Unknown"
            ),
            GitHubUser(
                113,
                "Oleksii Trekhleb",
                "trekhleb",
                17532,
                "17.532k",
                "San Francisco Bay Area",
            ),
        ]

    def format_candidate_output(self, user: GitHubUser) -> str:
        """Format candidate information for display"""
        return f"""
🎯 Random GitHub Candidate Found!

📊 Rank: #{user.rank}
👤 Name: {user.name}
🔗 Username: {user.username}
📈 Followers: {user.followers_display} ({user.followers:,})
📍 Location: {user.location or "Not specified"}
🏢 Company: {user.company or "Not specified"}

🌐 Profile: https://github.com/{user.username}
        """.strip()


class CandidateServiceAPI:
    """API layer for the candidate service"""

    def __init__(self):
        self.service = GitHubCandidateService()

    def get_random_candidate(self) -> Dict:
        """Get a random candidate as JSON response"""
        candidate = self.service.get_random_candidate()

        if not candidate:
            return {"success": False, "error": "No candidates found", "candidate": None}

        return {
            "success": True,
            "candidate": {
                "rank": candidate.rank,
                "name": candidate.name,
                "username": candidate.username,
                "followers": candidate.followers,
                "followers_display": candidate.followers_display,
                "location": candidate.location,
                "company": candidate.company,
                "profile_url": f"https://github.com/{candidate.username}",
            },
        }

    def get_multiple_candidates(self, count: int = 5) -> Dict:
        """Get multiple random candidates"""
        candidates_data = self.service.find_candidates()

        if not candidates_data:
            return {"success": False, "error": "No candidates found", "candidates": []}

        selected = random.sample(candidates_data, min(count, len(candidates_data)))

        return {
            "success": True,
            "candidates": [
                {
                    "rank": c.rank,
                    "name": c.name,
                    "username": c.username,
                    "followers": c.followers,
                    "followers_display": c.followers_display,
                    "location": c.location,
                    "company": c.company,
                    "profile_url": f"https://github.com/{c.username}",
                }
                for c in selected
            ],
        }


def main():
    """Main function for command line usage"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Find random GitHub candidates with up to 20k followers"
    )
    parser.add_argument(
        "--count", "-c", type=int, default=1, help="Number of candidates to return"
    )
    parser.add_argument(
        "--json", "-j", action="store_true", help="Output in JSON format"
    )
    parser.add_argument(
        "--service", "-s", action="store_true", help="Run as continuous service"
    )

    args = parser.parse_args()

    api = CandidateServiceAPI()

    if args.service:
        run_as_service(api)
    else:
        if args.count == 1:
            result = api.get_random_candidate()
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                if result["success"]:
                    candidate = result["candidate"]
                    service = GitHubCandidateService()
                    user = GitHubUser(
                        rank=candidate["rank"],
                        name=candidate["name"],
                        username=candidate["username"],
                        followers=candidate["followers"],
                        followers_display=candidate["followers_display"],
                        location=candidate["location"],
                        company=candidate["company"],
                    )
                    print(service.format_candidate_output(user))
                else:
                    print("Error: No candidates found")
        else:
            result = api.get_multiple_candidates(args.count)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                if result["success"]:
                    for i, candidate in enumerate(result["candidates"], 1):
                        print(f"\n--- Candidate {i} ---")
                        print(f"Rank: #{candidate['rank']}")
                        print(f"Name: {candidate['name']}")
                        print(f"Username: {candidate['username']}")
                        print(f"Followers: {candidate['followers_display']}")
                        print(f"Profile: https://github.com/{candidate['username']}")
                else:
                    print("Error: No candidates found")


def run_as_service(api: CandidateServiceAPI):
    """Run as a continuous service"""
    logger.info("Starting GitHub Candidate Finder Service...")
    logger.info("Press Ctrl+C to stop")

    try:
        while True:
            result = api.get_random_candidate()
            if result["success"]:
                candidate = result["candidate"]
                print(f"\n{'=' * 50}")
                print(f"🎯 New Candidate Found at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'=' * 50}")
                print(f"👤 {candidate['name']} (@{candidate['username']})")
                print(
                    f"📊 Rank: #{candidate['rank']} | Followers: {candidate['followers_display']}"
                )
                print(f"📍 {candidate['location'] or 'Location not specified'}")
                print(f"🏢 {candidate['company'] or 'Company not specified'}")
                print(f"🔗 https://github.com/{candidate['username']}")
            else:
                print("❌ No candidates found in this cycle")

            # Wait before next fetch
            time.sleep(300)  # 5 minutes

    except KeyboardInterrupt:
        logger.info("Service stopped by user")


if __name__ == "__main__":
    main()
