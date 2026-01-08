import hashlib
import time
from typing import List, Optional

from bs4 import BeautifulSoup
from loguru import logger
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from llm_engineering.domain.documents import ArticleDocument
from llm_engineering.domain.exceptions import ImproperlyConfigured
from llm_engineering.settings import settings

from .base import BaseSeleniumCrawler


class ConfluenceCrawler(BaseSeleniumCrawler):
    model = ArticleDocument

    def __init__(self, scroll_limit: int = 5) -> None:
        super().__init__(scroll_limit)
        self._authenticated = False

    def set_extra_driver_options(self, options) -> None:
        # undetected-chromedriver doesn't support experimental options like detach
        pass

    def login(self) -> None:
        """Log in to Confluence using username and password from settings."""
        if not settings.CONFLUENCE_USERNAME or not settings.CONFLUENCE_API_TOKEN:
            logger.warning(
                "Confluence credentials not found in settings. "
                "Set CONFLUENCE_USERNAME and CONFLUENCE_API_TOKEN environment variables."
            )
            return

        logger.info("Attempting to log in to Confluence...")

        # Navigate to Atlassian login page
        base_url = "https://id.atlassian.com/login"
        self.driver.get(base_url)
        time.sleep(3)

        try:
            # Enter username/email
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            username_field.clear()
            username_field.send_keys(settings.CONFLUENCE_USERNAME)

            # Click continue/submit button
            submit_button = self.driver.find_element(By.ID, "login-submit")
            submit_button.click()
            time.sleep(3)

            # Enter password (API token for Atlassian Cloud)
            password_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "password"))
            )
            password_field.clear()
            password_field.send_keys(settings.CONFLUENCE_API_TOKEN)

            # Click login button
            login_button = self.driver.find_element(By.ID, "login-submit")
            login_button.click()
            time.sleep(5)

            logger.info("Successfully logged in to Confluence")
            self._authenticated = True

        except TimeoutException as e:
            logger.error(f"Login timeout - could not find login form elements: {e}")
            raise ImproperlyConfigured(
                "Failed to log in to Confluence. Check your credentials and network connection."
            )
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise

    def _check_authentication(self) -> bool:
        """Check if user is authenticated to Confluence."""
        try:
            # Check for common authentication indicators
            # If we see a login form, we're not authenticated
            login_indicators = [
                "login",
                "sign-in",
                "authenticate",
            ]

            page_source_lower = self.driver.page_source.lower()
            has_login_form = any(indicator in page_source_lower for indicator in login_indicators)

            # Check for Confluence-specific authenticated elements
            try:
                # Look for the user profile menu (indicates logged in)
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "confluence-navigation"))
                )
                self._authenticated = True
                logger.info("User is authenticated to Confluence")
                return True
            except TimeoutException:
                pass

            if has_login_form:
                logger.warning(
                    "Authentication required. Please log in to Confluence manually, "
                    "or provide CONFLUENCE_API_TOKEN in settings."
                )
                self._authenticated = False
                return False

            # If no login form detected, assume authenticated
            self._authenticated = True
            return True

        except WebDriverException as e:
            logger.error(f"Error checking authentication: {e}")
            return False

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

    def _extract_page_links(self, space_url: str) -> List[str]:
        """Extract all page links from a Confluence space."""
        logger.info(f"Extracting page links from space: {space_url}")

        self.driver.get(space_url)
        time.sleep(3)

        # Check authentication and attempt login if needed
        if not self._check_authentication():
            logger.info("Not authenticated. Attempting to log in...")
            self.login()

            # Navigate back to the space URL after login
            self.driver.get(space_url)
            time.sleep(3)

            # Verify authentication after login
            if not self._check_authentication():
                raise ImproperlyConfigured(
                    "Authentication failed. Please check CONFLUENCE_USERNAME and CONFLUENCE_API_TOKEN settings."
                )

        self.scroll_page()

        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        # Find all page links in the space
        page_links = []

        # Look for page links in the page tree/navigation
        link_elements = soup.find_all("a", href=True)

        for link_elem in link_elements:
            href = link_elem.get("href", "")

            # Filter for Confluence page URLs
            if "/wiki/spaces/" in href and "/pages/" in href:
                # Convert relative URLs to absolute
                if href.startswith("/"):
                    base_url = space_url.split("/wiki")[0]
                    full_url = f"{base_url}{href}"
                else:
                    full_url = href

                # Remove query parameters for consistency
                full_url = full_url.split("?")[0]

                if full_url not in page_links:
                    page_links.append(full_url)

        logger.info(f"Found {len(page_links)} unique pages in space")
        return page_links

    def _extract_page_content(self, page_url: str) -> Optional[dict]:
        """Extract content from a single Confluence page."""
        logger.info(f"Extracting content from: {page_url}")

        self.driver.get(page_url)
        time.sleep(2)

        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        # Extract title
        title_elem = soup.find("h1", {"id": "title-text"}) or soup.find("h1")
        title = title_elem.get_text(strip=True) if title_elem else "Untitled"

        # Extract main content
        # Confluence uses different content areas depending on version
        content_elem = (
            soup.find("div", {"id": "main-content"})
            or soup.find("div", {"class": "wiki-content"})
            or soup.find("div", {"class": "contentLayout2"})
        )

        if not content_elem:
            logger.warning(f"Could not find content area for page: {page_url}")
            return None

        content_text = content_elem.get_text(separator="\n", strip=True)

        # Extract metadata
        metadata = {
            "Title": title,
            "Content": content_text,
            "URL": page_url,
        }

        # Try to extract author/last modified if available
        author_elem = soup.find("a", {"class": "confluence-userlink"})
        if author_elem:
            metadata["Last Modified By"] = author_elem.get_text(strip=True)

        return metadata

    def extract(self, link: str, **kwargs) -> None:
        """
        Extract pages from a Confluence space.

        Args:
            link: URL to Confluence space overview or specific page
            **kwargs: Must include 'user' with author information
        """
        logger.info(f"Starting Confluence crawl: {link}")

        user = kwargs.get("user")
        if not user:
            raise ValueError("User information is required for Confluence crawler")

        try:
            # Determine if this is a space URL or single page URL
            if "/spaces/" in link and "/overview" in link:
                # This is a space overview - extract all pages
                page_links = self._extract_page_links(link)

                logger.info(f"Processing {len(page_links)} pages from space")

                for page_url in page_links:
                    self._process_single_page(page_url, user)

            else:
                # This is a single page URL
                self._process_single_page(link, user)

        except Exception as e:
            logger.exception(f"Error during Confluence crawl: {e}")
            raise
        finally:
            self.driver.close()

        logger.info(f"Finished Confluence crawl: {link}")

    def _process_single_page(self, page_url: str, user) -> None:
        """Process a single Confluence page with change detection."""
        content_data = self._extract_page_content(page_url)

        if not content_data:
            logger.warning(f"Skipping page due to extraction failure: {page_url}")
            return

        # Calculate content hash
        content_str = content_data.get("Content", "")
        content_hash = self._calculate_content_hash(content_str)

        # Check if content has changed
        if not self._has_content_changed(page_url, content_hash):
            logger.info(f"Page content unchanged, skipping: {page_url}")
            return

        # Check if document exists
        existing_doc = self.model.find(link=page_url)

        if existing_doc:
            logger.info(f"Updating existing page: {page_url}")
            # Update the existing document
            existing_doc.content = content_data
            existing_doc.content_hash = content_hash
            existing_doc.save()
        else:
            logger.info(f"Saving new page: {page_url}")
            # Create new document
            instance = self.model(
                platform="confluence",
                content=content_data,
                link=page_url,
                content_hash=content_hash,
                author_id=user.id,
                author_full_name=user.full_name,
            )
            instance.save()

        logger.info(f"Successfully processed page: {page_url}")
