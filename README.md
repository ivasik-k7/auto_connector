# Follower Tracker

This repository contains a Python application designed to track followers of specific organizations on GitHub, gather relevant information about these followers, and store this data in a JSON file. The application also provides functionality to follow back users based on their programming language preference.

## Features

1. **Retrieve Followers**: The application connects to GitHub organizations and retrieves their followers.
2. **Fetch Follower Details**: For each follower, it gathers details including user ID, avatar URL, user type, and profile URL.
3. **Determine Top Language**: Identifies the top programming language used by each follower.
4. **Store Follower Information**: Saves the follower information to a JSON file for easy retrieval and analysis.
5. **Follow Users**: Based on the stored data, it follows users who have a specified programming language.

## Setup

### Prerequisites

- Python 3.7 or higher
- GitHub API token (with appropriate permissions)

### Installation

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

## Contributing

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-branch`).
3. Make your changes.
4. Commit your changes (`git commit -am 'Add new feature'`).
5. Push to the branch (`git push origin feature-branch`).
6. Create a new Pull Request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
