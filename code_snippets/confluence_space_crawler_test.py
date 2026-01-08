import os
import sys
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from llm_engineering.application.crawlers import ConfluenceCrawler
from llm_engineering.domain.documents import UserDocument


def main():
    """Test the Confluence crawler with the ACT Chargers space."""

    # Print start timestamp
    start_time = datetime.now()
    print("=" * 80)
    print(f"Confluence Crawler Test Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # Configuration
    confluence_space_url = "https://act-chargers.atlassian.net/wiki/spaces/AE/overview?mode=global"

    # Create user document
    user = UserDocument(first_name="Scott", last_name="C")
    print(f"User: {user.full_name}")
    print(f"User ID: {user.id}")
    print()

    # Initialize crawler with retry logic for slow-loading pages
    # scroll_limit: Increased from 5 to 15 to handle lengthy pages with embedded content
    # max_retries: Number of times to retry slow pages (default: 3)
    # page_load_timeout: Seconds to wait for a page to load before deferring it (default: 30)
    scroll_limit = 15
    max_retries = 3
    page_load_timeout = 30

    print(f"Initializing Confluence crawler...")
    print(f"  scroll_limit: {scroll_limit}")
    print(f"  max_retries: {max_retries} (slow pages will be deferred and retried)")
    print(f"  page_load_timeout: {page_load_timeout}s")
    crawler = ConfluenceCrawler(
        scroll_limit=scroll_limit,
        max_retries=max_retries,
        page_load_timeout=page_load_timeout
    )
    print()

    try:
        print(f"Starting crawl of space: {confluence_space_url}")
        print("-" * 80)
        print()

        # Extract content from the Confluence space
        crawler.extract(confluence_space_url, user=user)

        print()
        print("-" * 80)
        print("Crawl completed successfully!")

    except Exception as e:
        print()
        print("-" * 80)
        print(f"ERROR: Crawl failed with exception: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Print end timestamp and duration
        end_time = datetime.now()
        duration = end_time - start_time

        print()
        print("=" * 80)
        print(f"Confluence Crawler Test Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Duration: {duration}")
        print(f"Total Seconds: {duration.total_seconds():.2f}s")
        print("=" * 80)


if __name__ == "__main__":
    main()
