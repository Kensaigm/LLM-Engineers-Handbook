import os
import sys
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from llm_engineering.application.crawlers import ConfluenceAPICrawler
from llm_engineering.domain.documents import UserDocument


def main():
    """Test the Confluence API crawler (works with SSO)."""

    # Print start timestamp
    start_time = datetime.now()
    print("=" * 80)
    print(f"Confluence API Crawler Test Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # Configuration
    confluence_space_url = "https://act-chargers.atlassian.net/wiki/spaces/AE/overview?mode=global"

    print("📋 Configuration:")
    print(f"   Space URL: {confluence_space_url}")
    print()
    print("✓ Uses REST API - works with SSO!")
    print("✓ No browser needed - faster and more reliable")
    print("✓ Gets clean structured data from Confluence")
    print()

    # Create user document
    user = UserDocument(first_name="Scott", last_name="C")
    print(f"User: {user.full_name}")
    print(f"User ID: {user.id}")
    print()

    # Initialize API crawler
    print("Initializing Confluence API crawler...")
    print()

    try:
        crawler = ConfluenceAPICrawler(max_retries=3)
        print("✓ Crawler initialized")
        print()

    except Exception as e:
        print(f"❌ Failed to initialize crawler: {e}")
        print()
        print("Make sure your .env file has:")
        print("  CONFLUENCE_USERNAME=your-email@example.com")
        print("  CONFLUENCE_API_TOKEN=your-api-token")
        print("  CONFLUENCE_BASE_URL=https://act-chargers.atlassian.net/wiki")
        return

    try:
        print(f"Starting crawl of space: {confluence_space_url}")
        print("-" * 80)
        print()

        # Extract content from the Confluence space using API
        crawler.extract(confluence_space_url, user=user)

        print()
        print("-" * 80)
        print("✓ Crawl completed successfully!")

    except Exception as e:
        print()
        print("-" * 80)
        print(f"❌ ERROR: Crawl failed with exception: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Print end timestamp and duration
        end_time = datetime.now()
        duration = end_time - start_time

        print()
        print("=" * 80)
        print(f"Confluence API Crawler Test Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Duration: {duration}")
        print(f"Total Seconds: {duration.total_seconds():.2f}s")
        print("=" * 80)


if __name__ == "__main__":
    main()
