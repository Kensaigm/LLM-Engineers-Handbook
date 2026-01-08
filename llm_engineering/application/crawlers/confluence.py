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

    def __init__(self, scroll_limit: int = 5, max_retries: int = 3, page_load_timeout: int = 30, headless: bool = True) -> None:
        super().__init__(scroll_limit, headless=headless)
        self._authenticated = False
        self.max_retries = max_retries
        self.page_load_timeout = page_load_timeout

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
        logger.info(f"Username: {settings.CONFLUENCE_USERNAME}")

        # Navigate to Atlassian login page
        base_url = "https://id.atlassian.com/login"
        self.driver.get(base_url)

        # Wait for page to fully load
        logger.info("Waiting for login page to load...")
        time.sleep(5)

        try:
            # Wait for username/email field with multiple possible selectors
            logger.info("Looking for username field...")
            username_field = None

            # Try multiple selectors (Atlassian sometimes changes their form)
            selectors = [
                (By.ID, "username"),
                (By.NAME, "username"),
                (By.CSS_SELECTOR, "input[type='email']"),
                (By.CSS_SELECTOR, "input[name='username']"),
                (By.XPATH, "//input[@type='email' or @id='username']")
            ]

            for selector_type, selector_value in selectors:
                try:
                    username_field = WebDriverWait(self.driver, 15).until(
                        EC.element_to_be_clickable((selector_type, selector_value))
                    )
                    logger.info(f"Found username field with selector: {selector_type}={selector_value}")
                    break
                except TimeoutException:
                    continue

            if not username_field:
                raise TimeoutException("Could not find username field with any selector")

            # Clear and enter username
            username_field.clear()
            time.sleep(1)
            username_field.send_keys(settings.CONFLUENCE_USERNAME)
            time.sleep(1)
            logger.info("Username entered")

            # Click continue/submit button
            logger.info("Looking for submit button...")
            submit_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "login-submit"))
            )
            submit_button.click()
            logger.info("Clicked continue button")
            time.sleep(7)  # Wait for password page to load

            # Check for error messages on username page
            page_source = self.driver.page_source.lower()
            if "doesn't match" in page_source or "not found" in page_source or "incorrect" in page_source:
                logger.error("Username not recognized by Atlassian")
                raise ImproperlyConfigured(
                    f"Username '{settings.CONFLUENCE_USERNAME}' not recognized. "
                    "Verify this is your Atlassian account email."
                )

            # Enter password (API token for Atlassian Cloud)
            logger.info("Looking for password field...")
            password_field = None

            # Try multiple selectors for password field
            password_selectors = [
                (By.ID, "password"),
                (By.NAME, "password"),
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.XPATH, "//input[@type='password']")
            ]

            try:
                for selector_type, selector_value in password_selectors:
                    try:
                        password_field = WebDriverWait(self.driver, 15).until(
                            EC.element_to_be_clickable((selector_type, selector_value))
                        )
                        logger.info(f"Found password field with selector: {selector_type}={selector_value}")
                        break
                    except TimeoutException:
                        continue

                if not password_field:
                    raise TimeoutException("Could not find password field with any selector")
            except TimeoutException:
                # Save screenshot for debugging
                try:
                    screenshot_path = "/tmp/confluence_login_debug.png"
                    self.driver.save_screenshot(screenshot_path)
                    logger.error(f"Screenshot saved to: {screenshot_path}")
                except:
                    pass

                logger.error(f"Current URL: {self.driver.current_url}")
                logger.error("Could not find password field. The page might be showing an error or 2FA prompt.")
                raise ImproperlyConfigured(
                    "Could not find password field. Check if 2FA is enabled or if username is incorrect."
                )

            password_field.clear()
            time.sleep(1)
            password_field.send_keys(settings.CONFLUENCE_API_TOKEN)
            time.sleep(1)
            logger.info("API token entered")

            # Click login button
            logger.info("Looking for login button...")
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "login-submit"))
            )
            login_button.click()
            logger.info("Clicked login button")
            time.sleep(10)  # Wait longer for authentication to complete

            # Check if login was successful
            current_url = self.driver.current_url
            logger.info(f"After login, URL: {current_url}")

            # Check for error messages
            page_source = self.driver.page_source.lower()
            if "incorrect" in page_source or "invalid" in page_source or "wrong" in page_source:
                logger.error("Login credentials rejected")
                raise ImproperlyConfigured(
                    "API token rejected. Verify your token is correct and not expired. "
                    "Get a new token at: https://id.atlassian.com/manage-profile/security/api-tokens"
                )

            # If we're still on the login page, something went wrong
            if "login" in current_url or "authenticate" in current_url:
                logger.error("Still on login page after authentication attempt")
                raise ImproperlyConfigured(
                    "Login failed - still on login page. Check credentials or try generating a new API token."
                )

            logger.info("Successfully logged in to Confluence")
            self._authenticated = True

        except TimeoutException as e:
            logger.error(f"Login timeout - could not find login form elements: {e}")
            logger.error(f"Current URL: {self.driver.current_url}")
            raise ImproperlyConfigured(
                f"Failed to log in to Confluence. Timeout waiting for page elements. "
                f"Current URL: {self.driver.current_url}"
            )
        except ImproperlyConfigured:
            raise
        except Exception as e:
            logger.error(f"Login failed with unexpected error: {e}")
            logger.error(f"Current URL: {self.driver.current_url}")
            raise ImproperlyConfigured(
                f"Login failed: {str(e)}. Check your credentials and network connection."
            )

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

    def _is_page_loaded(self, soup: BeautifulSoup) -> bool:
        """Check if Confluence page has fully loaded with content."""
        # Check for loading indicators
        loading_indicators = soup.find_all(["div", "span"], class_=lambda x: x and ("loading" in x.lower() or "spinner" in x.lower()))
        if loading_indicators:
            return False

        # Check for actual content areas
        content_elem = (
            soup.find("div", {"id": "main-content"})
            or soup.find("div", {"class": "wiki-content"})
            or soup.find("div", {"class": "contentLayout2"})
        )

        # Page is loaded if we have content with substantial text
        if content_elem:
            content_text = content_elem.get_text(strip=True)
            # Require at least 10 characters of content to consider it loaded
            return len(content_text) > 10

        return False

    def _extract_page_content(self, page_url: str, retry_attempt: int = 0) -> Optional[dict]:
        """
        Extract content from a single Confluence page with timeout detection.

        Returns:
            dict: Page content if successful
            None: If page failed to load (should be retried)
        """
        logger.info(f"Extracting content from: {page_url} (attempt {retry_attempt + 1})")

        try:
            self.driver.get(page_url)

            # Wait for page to load with timeout
            start_time = time.time()
            max_wait = self.page_load_timeout
            wait_interval = 2

            while time.time() - start_time < max_wait:
                time.sleep(wait_interval)
                soup = BeautifulSoup(self.driver.page_source, "html.parser")

                if self._is_page_loaded(soup):
                    logger.info(f"Page loaded successfully: {page_url}")
                    break
            else:
                # Timeout reached
                elapsed = time.time() - start_time
                logger.warning(f"Page load timeout ({elapsed:.1f}s) for: {page_url}")
                return None

            # Extract title
            title_elem = soup.find("h1", {"id": "title-text"}) or soup.find("h1")
            title = title_elem.get_text(strip=True) if title_elem else "Untitled"

            # Extract main content
            content_elem = (
                soup.find("div", {"id": "main-content"})
                or soup.find("div", {"class": "wiki-content"})
                or soup.find("div", {"class": "contentLayout2"})
            )

            if not content_elem:
                logger.warning(f"Could not find content area for page: {page_url}")
                return None

            content_text = content_elem.get_text(separator="\n", strip=True)

            # Verify we have substantial content
            if len(content_text) < 10:
                logger.warning(f"Insufficient content extracted from: {page_url}")
                return None

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

        except Exception as e:
            logger.error(f"Error extracting content from {page_url}: {e}")
            return None

    def extract(self, link: str, **kwargs) -> None:
        """
        Extract pages from a Confluence space with intelligent retry logic.

        Pages that fail to load are automatically deferred to the end of the queue
        and retried after other pages have been processed. This helps with cloud-based
        systems that load recently-accessed pages faster than stale pages.

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
                # This is a space overview - extract all pages with retry logic
                page_links = self._extract_page_links(link)

                logger.info(f"Processing {len(page_links)} pages from space")

                # Process pages with deferred retry queue
                self._process_pages_with_retry(page_links, user)

            else:
                # This is a single page URL
                self._process_single_page(link, user, retry_attempt=0)

        except Exception as e:
            logger.exception(f"Error during Confluence crawl: {e}")
            raise
        finally:
            self.driver.close()

        logger.info(f"Finished Confluence crawl: {link}")

    def _process_pages_with_retry(self, page_urls: List[str], user) -> None:
        """
        Process pages with intelligent retry logic.

        Pages that fail to load are moved to the back of the queue and retried
        after other pages have been processed, up to max_retries times.
        """
        # Track retry attempts for each page
        retry_tracker = {url: 0 for url in page_urls}

        # Initialize queue with all pages
        queue = list(page_urls)
        processed_count = 0
        failed_permanently = []

        while queue:
            page_url = queue.pop(0)
            retry_attempt = retry_tracker[page_url]

            logger.info(f"Processing page {processed_count + 1}/{len(page_urls)}: {page_url}")

            success = self._process_single_page(page_url, user, retry_attempt=retry_attempt)

            if success:
                processed_count += 1
                logger.info(f"✓ Successfully processed ({processed_count}/{len(page_urls)})")
            else:
                # Page failed to load
                retry_tracker[page_url] += 1

                if retry_tracker[page_url] < self.max_retries:
                    # Defer to end of queue for retry
                    queue.append(page_url)
                    logger.warning(
                        f"⟳ Deferring page to end of queue (retry {retry_tracker[page_url]}/{self.max_retries}): {page_url}"
                    )
                else:
                    # Max retries reached
                    failed_permanently.append(page_url)
                    logger.error(
                        f"✗ Page failed after {self.max_retries} attempts, skipping: {page_url}"
                    )

        # Summary
        logger.info("=" * 80)
        logger.info(f"Crawl Summary:")
        logger.info(f"  Total pages: {len(page_urls)}")
        logger.info(f"  Successfully processed: {processed_count}")
        logger.info(f"  Failed permanently: {len(failed_permanently)}")

        if failed_permanently:
            logger.warning("Failed pages:")
            for url in failed_permanently:
                logger.warning(f"  - {url}")
        logger.info("=" * 80)

    def _process_single_page(self, page_url: str, user, retry_attempt: int = 0) -> bool:
        """
        Process a single Confluence page with change detection.

        Args:
            page_url: URL of the page to process
            user: User document for author information
            retry_attempt: Current retry attempt number

        Returns:
            bool: True if page was successfully processed, False if it should be retried
        """
        content_data = self._extract_page_content(page_url, retry_attempt=retry_attempt)

        if not content_data:
            logger.warning(f"Failed to extract content from page: {page_url}")
            return False  # Signal that page should be retried

        # Calculate content hash
        content_str = content_data.get("Content", "")
        content_hash = self._calculate_content_hash(content_str)

        # Check if content has changed
        if not self._has_content_changed(page_url, content_hash):
            logger.info(f"Page content unchanged, skipping: {page_url}")
            return True  # Successfully processed (no changes needed)

        # Check if document exists
        existing_doc = self.model.find(link=page_url)

        try:
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
            return True

        except Exception as e:
            logger.error(f"Error saving page to database: {page_url} - {e}")
            return False
