# GitHub Connector Service

This repository contains a Python service (`GitHubConnector`) that allows you to programmatically follow and unfollow GitHub users using the GitHub API.

## Features

- Follow GitHub users by username.
- Unfollow GitHub users by username.
- Uses GitHub API v3 for interactions.

## Setup

To use the GitHub Connector Service, follow these steps:

1. **Clone the repository:**

   ```bash
   git clone https://github.com/ivasik-k7/auto_connector.git .
   ```

2. **Install dependencies:**
   Ensure you have Python installed. Install required dependencies using pip:

   ```bash
   poetry install
   ```

3. **Set up environment variables:**
   Create a `.env` file in the root directory with your GitHub access token:

   ```
   GITHUB_TOKEN=your_github_access_token_here
   ```

4. **Usage:**
   Edit `main.py` or use in your own project to follow or unfollow GitHub users:

   ```python
   from dotenv import load_dotenv
   from app.services import GitHubConnector

   if __name__ == "__main__":
       load_dotenv()

       svc = GitHubConnector()
       users_to_follow = ["user1", "user2", "user3"]
       users_to_unfollow = ["user4", "user5"]

       for user in users_to_follow:
           svc.follow(user)

       for user in users_to_unfollow:
           svc.unfollow(user)
   ```

5. **Documentation:**
   - `GitHubConnector` class methods:
     - `follow(username)`: Follows a GitHub user.
     - `unfollow(username)`: Unfollows a GitHub user.
