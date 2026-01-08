import hashlib
import requests
from typing import List, Optional, Dict
from urllib.parse import urlparse

from loguru import logger

from llm_engineering.domain.documents import ArticleDocument
from llm_engineering.domain.exceptions import ImproperlyConfigured
from llm_engineering.settings import settings

from .base import BaseCrawler


class ConfluenceAPICrawler(BaseCrawler):
    """
    Confluence crawler using REST API instead of Selenium.

    This approach works with SSO-enabled Confluence instances where
    browser-based authentication doesn't work with API tokens.

    Required settings:
        CONFLUENCE_USERNAME: Your Atlassian email
        CONFLUENCE_API_TOKEN: API token from https://id.atlassian.com/manage-profile/security/api-tokens
        CONFLUENCE_BASE_URL: Your Confluence URL (e.g., https://act-chargers.atlassian.net/wiki)
    """

    model = ArticleDocument

    def __init__(self, max_retries: int = 3) -> None:
        super().__init__()
        self.max_retries = max_retries
        self.session = requests.Session()

        # Validate credentials
        if not settings.CONFLUENCE_USERNAME or not settings.CONFLUENCE_API_TOKEN:
            raise ImproperlyConfigured(
                "CONFLUENCE_USERNAME and CONFLUENCE_API_TOKEN must be set in .env file"
            )

        # Setup authentication
        self.session.auth = (settings.CONFLUENCE_USERNAME, settings.CONFLUENCE_API_TOKEN)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

        # Extract base URL from settings or default
        self.base_url = getattr(settings, 'CONFLUENCE_BASE_URL', None)
        if not self.base_url:
            logger.warning("CONFLUENCE_BASE_URL not set. Will extract from space URL.")

    def _extract_base_url(self, space_url: str) -> str:
        """Extract base Confluence URL from a space URL."""
        parsed = urlparse(space_url)
        # e.g., https://act-chargers.atlassian.net
        return f"{parsed.scheme}://{parsed.netloc}"

    def _get_space_key(self, space_url: str) -> str:
        """Extract space key from space URL."""
        # Example: https://act-chargers.atlassian.net/wiki/spaces/AE/overview
        # Space key is "AE"
        parts = space_url.split('/spaces/')
        if len(parts) > 1:
            space_key = parts[1].split('/')[0].split('?')[0]
            return space_key
        raise ValueError(f"Could not extract space key from URL: {space_url}")

    def _test_connection(self) -> bool:
        """Test API connection with credentials."""
        try:
            url = f"{self.base_url}/rest/api/space"
            response = self.session.get(url, timeout=10)

            if response.status_code == 401:
                logger.error("Authentication failed. Check your API token.")
                return False
            elif response.status_code == 403:
                logger.error("Access denied. Check your permissions.")
                return False
            elif response.status_code == 200:
                logger.info("✓ Successfully connected to Confluence API")
                return True
            else:
                logger.warning(f"Unexpected response: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def _get_space_pages(self, space_key: str) -> List[Dict]:
        """Get all pages in a space using Confluence REST API."""
        logger.info(f"Fetching pages for space: {space_key}")

        all_pages = []
        start = 0
        limit = 100  # Max results per request

        while True:
            url = f"{self.base_url}/rest/api/content"
            params = {
                "spaceKey": space_key,
                "type": "page",
                "status": "current",
                "expand": "version,body.storage,body.view,space",
                "start": start,
                "limit": limit
            }

            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()

                data = response.json()
                results = data.get("results", [])

                if not results:
                    break

                all_pages.extend(results)
                logger.info(f"Fetched {len(all_pages)} pages so far...")

                # Check if there are more pages
                links = data.get("_links", {})
                if "next" not in links:
                    break

                start += limit

            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching pages: {e}")
                break

        logger.info(f"Found {len(all_pages)} total pages in space '{space_key}'")
        return all_pages

    def _get_page_content(self, page_id: str) -> Optional[Dict]:
        """Get full content of a specific page."""
        url = f"{self.base_url}/rest/api/content/{page_id}"
        params = {
            "expand": "body.storage,body.view,version,space,history.lastUpdated"
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching page {page_id}: {e}")
            return None

    def _calculate_content_hash(self, content: str) -> str:
        """Calculate MD5 hash of content for change detection."""
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _has_content_changed(self, link: str, new_hash: str) -> bool:
        """Check if content has changed by comparing hashes."""
        existing_doc = self.model.find(link=link)
        if existing_doc is None:
            return True  # New document

        if existing_doc.content_hash is None:
            return True  # No hash stored, consider it changed

        return existing_doc.content_hash != new_hash

    def _extract_text_from_html(self, html: str) -> str:
        """Extract clean text from Confluence HTML storage format."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # Remove scripts, styles, etc.
        for element in soup(["script", "style", "meta", "link"]):
            element.decompose()

        # Get text with proper spacing
        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)

    def extract(self, link: str, **kwargs) -> None:
        """
        Extract pages from a Confluence space using REST API.

        Args:
            link: URL to Confluence space (e.g., https://domain.atlassian.net/wiki/spaces/AE/overview)
            **kwargs: Must include 'user' with author information
        """
        user = kwargs.get("user")
        if not user:
            raise ValueError("User information is required for Confluence crawler")

        logger.info(f"Starting Confluence API crawl: {link}")

        # Extract base URL and space key
        if not self.base_url:
            self.base_url = self._extract_base_url(link)

        space_key = self._get_space_key(link)
        logger.info(f"Space key: {space_key}")
        logger.info(f"Base URL: {self.base_url}")

        # Test connection
        if not self._test_connection():
            raise ImproperlyConfigured(
                "Failed to connect to Confluence API. Check your credentials and base URL."
            )

        # Get all pages in space
        pages = self._get_space_pages(space_key)

        if not pages:
            logger.warning(f"No pages found in space '{space_key}'")
            return

        logger.info(f"Processing {len(pages)} pages...")

        # Process each page
        successful = 0
        skipped = 0
        failed = 0

        for i, page in enumerate(pages, 1):
            page_id = page.get("id")
            page_title = page.get("title", "Untitled")

            logger.info(f"[{i}/{len(pages)}] Processing: {page_title}")

            try:
                # Get full page content
                full_page = self._get_page_content(page_id)
                if not full_page:
                    failed += 1
                    continue

                # Extract content
                body = full_page.get("body", {})
                storage = body.get("storage", {}) or body.get("view", {})
                html_content = storage.get("value", "")

                if not html_content:
                    logger.warning(f"No content found for page: {page_title}")
                    skipped += 1
                    continue

                # Convert HTML to text
                text_content = self._extract_text_from_html(html_content)

                # Build page URL
                page_url = f"{self.base_url}/wiki/spaces/{space_key}/pages/{page_id}"

                # Calculate content hash
                content_hash = self._calculate_content_hash(text_content)

                # Check if content has changed
                if not self._has_content_changed(page_url, content_hash):
                    logger.info(f"Page content unchanged, skipping: {page_title}")
                    skipped += 1
                    continue

                # Prepare metadata
                version = full_page.get("version", {})
                history = full_page.get("history", {})
                last_updated = history.get("lastUpdated", {})

                content_data = {
                    "Title": page_title,
                    "Content": text_content,
                    "URL": page_url,
                    "Page ID": page_id,
                    "Version": version.get("number"),
                    "Last Modified": last_updated.get("when"),
                    "Last Modified By": last_updated.get("by", {}).get("displayName"),
                }

                # Save or update document
                existing_doc = self.model.find(link=page_url)

                if existing_doc:
                    logger.info(f"Updating existing page: {page_title}")
                    existing_doc.content = content_data
                    existing_doc.content_hash = content_hash
                    existing_doc.save()
                else:
                    logger.info(f"Saving new page: {page_title}")
                    instance = self.model(
                        platform="confluence",
                        content=content_data,
                        link=page_url,
                        content_hash=content_hash,
                        author_id=user.id,
                        author_full_name=user.full_name,
                    )
                    instance.save()

                successful += 1
                logger.info(f"✓ Successfully processed: {page_title}")

            except Exception as e:
                logger.error(f"Failed to process page '{page_title}': {e}")
                failed += 1

        # Summary
        logger.info("=" * 80)
        logger.info("Confluence API Crawl Summary:")
        logger.info(f"  Total pages: {len(pages)}")
        logger.info(f"  Successfully processed: {successful}")
        logger.info(f"  Skipped (unchanged): {skipped}")
        logger.info(f"  Failed: {failed}")
        logger.info("=" * 80)

        logger.info(f"Finished Confluence API crawl: {link}")
