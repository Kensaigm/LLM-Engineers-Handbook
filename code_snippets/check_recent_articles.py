import os
import sys
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from llm_engineering.infrastructure.db.mongo import connection
from llm_engineering.settings import settings


def check_recent_articles(limit=20, platform="confluence"):
    """
    Check the most recently modified articles in MongoDB.

    Args:
        limit: Number of articles to retrieve (default: 20)
        platform: Filter by platform (default: "confluence")
    """
    print("=" * 80)
    print(f"Checking {limit} Most Recently Modified Articles")
    print("=" * 80)
    print()

    # Get database connection
    db = connection.get_database(settings.DATABASE_NAME)
    collection = db.articles

    # Total count
    total_count = collection.count_documents({"platform": platform})
    print(f"📊 Total {platform} articles in database: {total_count}")
    print()

    # Query for recent articles
    # Sort by the "Last Modified" field inside the content object
    # MongoDB query: sort by nested field content.Last Modified
    query = {"platform": platform}

    # Try to sort by Last Modified in content, fallback to _id if not present
    pipeline = [
        {"$match": query},
        {"$addFields": {
            "lastModifiedDate": {
                "$dateFromString": {
                    "dateString": "$content.Last Modified",
                    "onError": None,
                    "onNull": None
                }
            }
        }},
        {"$sort": {"lastModifiedDate": -1}},
        {"$limit": limit}
    ]

    try:
        articles = list(collection.aggregate(pipeline))
    except Exception as e:
        print(f"⚠️  Could not sort by Last Modified date: {e}")
        print("Falling back to sorting by document insertion order (_id)...")
        print()
        articles = list(collection.find(query).sort("_id", -1).limit(limit))

    if not articles:
        print("❌ No articles found!")
        return

    print(f"📄 Showing {len(articles)} most recent articles:")
    print("-" * 80)
    print()

    for i, article in enumerate(articles, 1):
        content = article.get("content", {})

        title = content.get("Title", "Untitled")
        url = content.get("URL", article.get("link", "No URL"))
        page_id = content.get("Page ID", "Unknown")
        version = content.get("Version", "Unknown")
        last_modified = content.get("Last Modified", "Unknown")
        modified_by = content.get("Last Modified By", "Unknown")

        print(f"{i}. {title}")
        print(f"   Page ID: {page_id}")
        print(f"   Version: {version}")
        print(f"   Last Modified: {last_modified}")
        print(f"   Modified By: {modified_by}")
        print(f"   URL: {url}")

        # Show content preview
        content_text = content.get("Content", "")
        if content_text:
            preview = content_text[:150].replace("\n", " ")
            print(f"   Preview: {preview}...")

        print()

    print("-" * 80)
    print("✓ Done!")
    print()


if __name__ == "__main__":
    # Configuration - Edit these variables as needed
    NUM_ARTICLES = 20  # Change this to 5, 10, 20, etc.
    PLATFORM = "confluence"  # Change to filter by different platform

    check_recent_articles(limit=NUM_ARTICLES, platform=PLATFORM)
