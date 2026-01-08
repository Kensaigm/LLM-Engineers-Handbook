import os
import sys
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from llm_engineering.application.crawlers import ConfluenceCrawler
from llm_engineering.domain.documents import UserDocument
from llm_engineering.settings import settings


def main():
    """Test Confluence authentication only - no page crawling."""

    print("=" * 80)
    print("Confluence Login Test")
    print("=" * 80)
    print()

    # Check if credentials are configured
    print("Checking configuration...")
    if not settings.CONFLUENCE_USERNAME:
        print("❌ CONFLUENCE_USERNAME is not set in .env file")
        print("   Add: CONFLUENCE_USERNAME=your-email@example.com")
        return
    else:
        print(f"✓ CONFLUENCE_USERNAME: {settings.CONFLUENCE_USERNAME}")

    if not settings.CONFLUENCE_API_TOKEN:
        print("❌ CONFLUENCE_API_TOKEN is not set in .env file")
        print("   Get token from: https://id.atlassian.com/manage-profile/security/api-tokens")
        return
    else:
        # Show first/last 4 chars of token for verification
        token = settings.CONFLUENCE_API_TOKEN
        masked = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "****"
        print(f"✓ CONFLUENCE_API_TOKEN: {masked}")

    print()
    print("-" * 80)
    print("Initializing crawler...")
    print()
    print("🔍 Running in VISIBLE mode so you can see what's happening...")
    print("   (The browser window will open)")
    print()

    # Create crawler in non-headless mode for debugging
    crawler = ConfluenceCrawler(scroll_limit=5, headless=False)

    print("Browser started successfully")
    print()
    print("-" * 80)
    print("Attempting login to Atlassian...")
    print("Watch the browser window to see the login process...")
    print()

    try:
        # Attempt login
        crawler.login()

        print()
        print("-" * 80)
        print("✓ LOGIN SUCCESSFUL!")
        print()
        print("You can now run the full crawler with:")
        print("  python code_snippets/confluence_space_crawler_test.py")
        print()

        # Keep browser open for 5 seconds so you can see the result
        print("Keeping browser open for 5 seconds for verification...")
        import time
        time.sleep(5)

    except Exception as e:
        print()
        print("-" * 80)
        print(f"❌ LOGIN FAILED: {e}")
        print()
        print("Debug information:")
        print(f"  Username: {settings.CONFLUENCE_USERNAME}")
        print(f"  Token length: {len(settings.CONFLUENCE_API_TOKEN)} characters")
        print()
        print("Common issues:")
        print("  1. API token was copied incorrectly (check for extra spaces)")
        print("  2. Token was revoked or expired")
        print("  3. Username/email doesn't match Atlassian account")
        print("  4. Network/firewall blocking Atlassian")
        print()
        print("Screenshot saved to: confluence_login_error.png")

        # Try to save a screenshot for debugging
        try:
            screenshot_path = os.path.join(os.path.dirname(__file__), "confluence_login_error.png")
            crawler.driver.save_screenshot(screenshot_path)
            print(f"Check the screenshot for visual debugging")
        except:
            print("Could not save screenshot")

        import traceback
        print()
        print("Full traceback:")
        traceback.print_exc()

    finally:
        try:
            crawler.driver.close()
            print()
            print("Browser closed")
        except:
            pass

    print("=" * 80)


if __name__ == "__main__":
    main()
