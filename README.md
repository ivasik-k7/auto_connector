# 🚀 Advanced GitHub Follower Sync

A high-performance, flexible, and feature-rich tool for synchronizing and managing GitHub followers with advanced filtering, data enrichment, and automation capabilities.

## ✨ Key Features

### 🎯 Core Functionality

- **Multi-source Data Enrichment** - Aggregate user data from multiple APIs
- **Concurrent Processing** - High-performance parallel processing with ThreadPoolExecutor
- **Flexible Processing Strategies** - Fast, Balanced, or Comprehensive data collection
- **Smart Follow Automation** - Rule-based following with advanced filters
- **Comprehensive Metrics** - Real-time processing statistics and performance tracking

### 🔍 Data Collection

- Basic user information (name, bio, location, company)
- Programming language statistics
- Social media link extraction
- Email discovery from public events
- Contribution statistics (stars, forks, repos)
- Language distribution across repositories

### 🎛️ Advanced Filtering

- **Whitelist/Blacklist** - Explicit user inclusion/exclusion
- **Language Filters** - Target specific programming languages
- **Repository Thresholds** - Min/max repository counts
- **Follower Requirements** - Filter by follower/following counts
- **Keyword Matching** - Bio keyword filters (required/excluded)
- **Account Age** - Minimum account age requirement
- **Custom Filters** - Programmable custom filter functions

### 🛡️ Safety Features

- Rate limit protection with automatic waiting
- Dry-run mode for testing
- Error threshold limits
- Follow count limits per run
- Duplicate follow prevention
- Comprehensive error handling and logging

## 📦 Installation

```bash
# Clone the repository
git clone <repository-url>
cd github-follower-sync

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment file
cp .env.example .env
# Edit .env with your GitHub token and settings
```

## 🔑 GitHub Token Setup

1. Go to [GitHub Settings → Tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select required scopes:
   - ✅ `user` - Required for basic user info
   - ✅ `user:follow` - Required for auto-follow
   - ✅ `read:org` - Optional, for organization data
4. Generate and copy the token
5. Add to `.env`: `GITHUB_TOKEN=ghp_your_token_here`

## 🚀 Quick Start

### Basic Usage

```bash
# Process followers with default settings
python github_follower_sync_v2.py
```

### Common Use Cases

#### 1. Fast Data Collection (No Following)

```bash
# In .env:
PROCESSING_STRATEGY=fast
FOLLOW_ENABLED=false
MAX_WORKERS=20
TARGET_ORGANIZATIONS=["user1", "org2"]
```

#### 2. Auto-Follow Python Developers

```bash
# In .env:
PROCESSING_STRATEGY=balanced
FOLLOW_ENABLED=true
FOLLOW_LANGUAGES=["Python"]
FOLLOW_MIN_REPOS=5
FOLLOW_MIN_FOLLOWERS=10
```

#### 3. Comprehensive Research Data

```bash
# In .env:
PROCESSING_STRATEGY=comprehensive
ENABLE_EMAIL_EXTRACTION=true
ENABLE_LANGUAGE_STATS=true
ENABLE_CONTRIBUTION_STATS=true
MAX_WORKERS=5
```

#### 4. Selective Following with Filters

```bash
# In .env:
FOLLOW_ENABLED=true
FOLLOW_MIN_REPOS=10
FOLLOW_MIN_FOLLOWERS=50
FOLLOW_MIN_ACCOUNT_AGE_DAYS=180
FOLLOW_REQUIRED_KEYWORDS=["developer", "engineer"]
FOLLOW_EXCLUDE_KEYWORDS=["bot", "spam"]
```

## 📊 Processing Strategies

| Strategy          | Speed  | Data Completeness | API Calls | Best For                    |
| ----------------- | ------ | ----------------- | --------- | --------------------------- |
| **Fast**          | ⚡⚡⚡ | Basic             | Minimal   | Quick scans, large lists    |
| **Balanced**      | ⚡⚡   | Good              | Moderate  | Daily operations (default)  |
| **Comprehensive** | ⚡     | Complete          | Maximum   | Research, detailed analysis |

### Strategy Details

**Fast Mode**

- Top programming language only
- Minimal API calls
- Best for 500+ users
- ~0.5s per user

**Balanced Mode** (Recommended)

- Complete user profile
- Top language + basic stats
- Good performance
- ~1-2s per user

**Comprehensive Mode**

- Full enrichment
- Language distribution
- Contribution statistics
- Social link extraction
- ~3-5s per user

## 🎛️ Configuration Reference

### Environment Variables

All configuration is done through `.env` file. See `.env.example` for complete reference.

**Essential Settings:**

```bash
GITHUB_TOKEN=ghp_xxx              # Required: Your GitHub token
TARGET_ORGANIZATIONS=["user1"]    # Organizations to process
MAX_WORKERS=10                    # Concurrent workers (1-50)
PROCESSING_STRATEGY=balanced      # fast|balanced|comprehensive
```

**Follow Automation:**

```bash
FOLLOW_ENABLED=false              # Enable auto-follow
FOLLOW_DELAY=1.0                  # Delay between follows (seconds)
MAX_FOLLOWS_PER_RUN=100          # Safety limit
```

**Filters:**

```bash
FOLLOW_LANGUAGES=["Python"]       # Language filter
FOLLOW_MIN_REPOS=5                # Min repository count
FOLLOW_MIN_FOLLOWERS=10           # Min follower count
FOLLOW_MIN_ACCOUNT_AGE_DAYS=30   # Min account age
```

### Programmatic Configuration

```python
from app.utils.config import Config

# Load from environment
config = Config.load()

# Load from JSON file
config = Config.from_file('custom_config.json')

# Customize in code
config.MAX_WORKERS = 20
config.FOLLOW_CONFIG['languages'] = ['Python', 'JavaScript']
```

## 📈 Output

### CSV Output

Processed user data is saved to CSV (default: `examples/profiles.csv`):

```csv
id,login,name,bio,company,location,public_repos,followers,following,top_language,total_stars,url,created_at
123,username,Full Name,Bio text,@Company,Location,42,150,80,Python,250,https://github.com/username,2020-01-01
```

### Console Output

```
🚀 Starting Advanced Follower Sync
   Strategy: balanced
   Organizations: org1, org2
   Max Workers: 10

✅ GitHub token validated!
   Authenticated as: your_username
   Rate limit: 4850/5000 requests remaining

📥 Loading existing following list...
✅ Loaded 156 existing follows

📊 Fetching followers for: org1
✅ Found 342 followers for org1

✅ Processed user1 (1/342) [1.23s]
👥 Followed user2: All filters passed
⏭️  Skipped user3: Language mismatch
✅ Processed user4 (4/342) [0.98s]

======================================================================
📈 Processing Summary:
======================================================================
  Total Users:            342
  Successfully Processed: 340
  Failed:                 2
  Followed:               85
  Skipped:                200
  Already Following:      55
  Duration:               456.78s
  Processing Rate:        0.74 users/sec
======================================================================
```

## 🔧 Advanced Usage

### Custom Filters

```python
from github_follower_sync_v2 import FollowFilter, UserProfile

def custom_filter(profile: UserProfile) -> bool:
    """Custom filter logic"""
    # Only follow users with Python as top language
    # AND more than 100 total stars
    return (
        profile.top_language == "Python" and
        profile.total_stars > 100
    )

# Apply custom filter
filter_config = config.FOLLOW_CONFIG
follow_filter = FollowFilter(filter_config)
follow_filter.custom_filter = custom_filter
```

### Batch Processing

```python
from github_follower_sync_v2 import FollowerProcessor

processor = FollowerProcessor(
    activity_service,
    stats_service,
    connector,
    config,
    strategy=ProcessingStrategy.BALANCED
)

# Process specific organization
with StorageManager("output.csv") as file_manager:
    processor.process_organization("organization_name", file_manager)
```

### Progress Monitoring

```python
# Access real-time metrics
metrics = processor.metrics

print(f"Processed: {metrics.processed}/{metrics.total_users}")
print(f"Rate: {metrics.processing_rate:.2f} users/sec")
print(f"Success Rate: {metrics.processed/(metrics.processed+metrics.failed)*100:.1f}%")
```

## 🐛 Troubleshooting

### Rate Limiting

**Problem:** `RateLimitExceeded` errors

**Solutions:**

1. Reduce `MAX_WORKERS` (try 5 or fewer)
2. Increase `FOLLOW_DELAY` to 2.0 or higher
3. Use `PROCESSING_STRATEGY=fast` for less API calls
4. Wait for rate limit reset (shown in error message)

### Token Issues

**Problem:** `401 Unauthorized` errors

**Solutions:**

1. Verify token in `.env` is correct
2. Check token hasn't expired
3. Ensure token has required scopes (`user`, `user:follow`)
4. Regenerate token if needed

### Performance Issues

**Problem:** Slow processing speed

**Solutions:**

1. Use `PROCESSING_STRATEGY=fast`
2. Increase `MAX_WORKERS` (carefully, watch rate limits)
3. Disable expensive features:
   - `ENABLE_EMAIL_EXTRACTION=false`
   - `ENABLE_CONTRIBUTION_STATS=false`
4. Process smaller batches

### Memory Issues

**Problem:** High memory usage

**Solutions:**

1. Reduce `MAX_WORKERS`
2. Disable `ENABLE_CACHING`
3. Process organizations one at a time
4. Use `PROCESS_IN_BATCHES=true`

## 📊 Performance Benchmarks

Tested on standard hardware (4 cores, 8GB RAM):

| Users | Strategy      | Workers | Time | Rate   |
| ----- | ------------- | ------- | ---- | ------ |
| 100   | Fast          | 20      | 50s  | 2.0/s  |
| 100   | Balanced      | 10      | 120s | 0.83/s |
| 100   | Comprehensive | 5       | 380s | 0.26/s |
| 500   | Fast          | 20      | 240s | 2.08/s |
| 500   | Balanced      | 10      | 650s | 0.77/s |

_Rate = users processed per second_

## 🔒 Security & Privacy

- **Token Security**: Never commit `.env` to version control
- **Rate Limiting**: Built-in protection against API abuse
- **Data Privacy**: Only collects public GitHub data
- **Local Storage**: All data stored locally in CSV
- **No Third Parties**: Direct GitHub API access only

## 🤝 Contributing

Contributions welcome! Areas for improvement:

- Additional data sources
- More filter types
- Performance optimizations
- Better error recovery
- Database storage options
- Web UI dashboard

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- GitHub API for comprehensive user data
- github-readme-stats for language statistics
- Community for feature requests and bug reports

## 📞 Support

- Issues: [GitHub Issues](https://github.com/your-repo/issues)
- Discussions: [GitHub Discussions](https://github.com/your-repo/discussions)
- Documentation: [Wiki](https://github.com/your-repo/wiki)

---

Made with ❤️ for the GitHub community
