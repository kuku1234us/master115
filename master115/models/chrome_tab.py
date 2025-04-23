# master115/models/chrome_tab.py
from __future__ import annotations # For Type Hinting Chrome115Browser

import time
from typing import Optional, Tuple, List, TYPE_CHECKING, Union # Added Union
from pathlib import Path
from datetime import datetime

from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains

# Framework imports (assuming Logger is accessible)
from qt_base_app.models import Logger

# Type hint for Chrome115Browser without circular import issues
if TYPE_CHECKING:
    from selenium import webdriver # Needed for driver type hint
    from .chrome115_browser import Chrome115Browser

Locator = Tuple[By, str]
ElementParam = Union[WebElement, Locator]
IFrameParam = Union[str, int, Locator]

class ChromeTab:
    """
    Represents a single tab within the Chrome115Browser.

    Handles interactions specific to this tab's content,
    ensuring the browser's focus is set correctly before acting.
    Meant to be subclassed for site-specific scraping logic.
    """

    def __init__(self, browser: 'Chrome115Browser', handle: str):
        """Initialize a ChromeTab instance."""
        self.browser = browser
        self.handle = handle
        self.logger = Logger.instance() # Get logger instance
        # Generate a unique-ish caller name for logs related to this tab
        self.caller_name = f"ChromeTab({self.handle[-6:]})"
        self.logger.info(self.caller_name, f"Initialized for handle: {self.handle}")

    def get_handle(self) -> str:
        """Returns the unique window handle for this tab."""
        return self.handle

    def _ensure_focus_and_get_driver(self) -> Optional[webdriver.Chrome]:
        """
        Internal helper: Switches browser focus to this tab and returns the WebDriver.

        Returns:
            The WebDriver instance if focus is successful and browser is running, None otherwise.
        """
        if not self.browser.switch_focus_to(self):
            self.logger.error(self.caller_name, f"Failed to switch focus to tab {self.handle}. Aborting action.")
            return None
        driver = self.browser.get_webdriver()
        if not driver:
             self.logger.error(self.caller_name, "Browser driver is not available after focus switch. Aborting action.")
             return None
        return driver

    def navigate(self, url: str) -> bool:
        """Navigates this tab to the specified URL."""
        driver = self._ensure_focus_and_get_driver()
        if not driver:
            return False
        try:
            # self.logger.debug(self.caller_name, f"Navigating to: {url}")
            driver.get(url)
            return True
        except WebDriverException as e:
             self.logger.error(self.caller_name, f"WebDriverException during navigation to {url}: {e}", exc_info=False)
             return False
        except Exception as e:
            self.logger.error(self.caller_name, f"Unexpected error during navigation to {url}: {e}", exc_info=True)
            return False

    def get_url(self) -> Optional[str]:
        """Gets the current URL of this tab."""
        driver = self._ensure_focus_and_get_driver()
        if not driver:
            return None
        try:
            return driver.current_url
        except Exception as e:
            self.logger.error(self.caller_name, f"Error getting current URL: {e}", exc_info=True)
            return None

    def get_title(self) -> Optional[str]:
        """Gets the current title of this tab."""
        driver = self._ensure_focus_and_get_driver()
        if not driver:
            return None
        try:
            return driver.title
        except Exception as e:
            self.logger.error(self.caller_name, f"Error getting title: {e}", exc_info=True)
            return None

    def get_source(self) -> Optional[str]:
        """Gets the full HTML source of the current page/frame in this tab."""
        driver = self._ensure_focus_and_get_driver()
        if not driver:
            return None
        try:
            return driver.page_source
        except Exception as e:
            self.logger.error(self.caller_name, f"Error getting page source: {e}", exc_info=True)
            return None

    def save_source(self, directory: str = "./page_repo", filename_prefix: Optional[str] = None) -> Optional[Path]:
        """Saves the current page source to a timestamped HTML file."""
        source = self.get_source()
        if source is None:
             self.logger.error(self.caller_name, "Failed to save page source: Could not retrieve source.")
             return None

        current_url = self.get_url() or "unknown_url"
        current_title = self.get_title() or "unknown_title"

        try:
            repo_dir = Path(directory)
            repo_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Determine filename base
            if filename_prefix:
                 base = filename_prefix
            else:
                # Basic filename cleaning from title or URL
                safe_part = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in current_title)
                if not safe_part or safe_part.startswith('_'): # Fallback to URL if title is bad
                     safe_url_part = current_url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "-").replace("?", "_").replace("=", "-")
                     safe_part = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in safe_url_part)

                max_len = 60
                base = safe_part[:max_len] if len(safe_part) > max_len else safe_part

            filename = repo_dir / f"{base}_{timestamp}.html"

            with open(filename, "w", encoding="utf-8") as f:
                f.write(source)

            self.logger.info(self.caller_name, f"Page source saved to: {filename}")
            return filename

        except Exception as e:
            self.logger.error(self.caller_name, f"Failed to save page source to file: {e}", exc_info=True)
            return None

    def find_element(self, by: By, value: str, wait_time: int = 10) -> Optional[WebElement]:
        """Finds a single element in this tab, waiting for presence."""
        driver = self._ensure_focus_and_get_driver()
        if not driver:
            return None
        try:
            wait = WebDriverWait(driver, wait_time)
            element = wait.until(EC.presence_of_element_located((by, value)))
            return element
        except TimeoutException:
            # self.logger.debug(self.caller_name, f"Timeout waiting for element ({by}='{value}')")
            return None
        except Exception as e:
            self.logger.error(self.caller_name, f"Error finding element ({by}='{value}'): {e}", exc_info=False)
            return None

    def find_elements(self, by: By, value: str, wait_time: int = 10) -> List[WebElement]:
        """Finds multiple elements in this tab, waiting for presence."""
        driver = self._ensure_focus_and_get_driver()
        if not driver:
            return []
        try:
            wait = WebDriverWait(driver, wait_time)
            elements = wait.until(EC.presence_of_all_elements_located((by, value)))
            return elements
        except TimeoutException:
            # self.logger.debug(self.caller_name, f"Timeout waiting for elements ({by}='{value}')")
            return []
        except Exception as e:
            self.logger.error(self.caller_name, f"Error finding elements ({by}='{value}'): {e}", exc_info=False)
            return []

    def click(self, element: ElementParam, wait_time: int = 10) -> bool:
        """Waits for an element to be clickable and clicks it."""
        driver = self._ensure_focus_and_get_driver()
        if not driver:
            return False

        try:
            wait = WebDriverWait(driver, wait_time)
            target_element: Optional[WebElement] = None
            locator_for_msg = 'WebElement provided'

            if isinstance(element, WebElement):
                # If WebElement is passed, wait for it directly
                target_element = wait.until(EC.element_to_be_clickable(element))
            elif isinstance(element, tuple) and len(element) == 2:
                # If locator tuple is passed, wait using the locator
                locator_for_msg = element
                target_element = wait.until(EC.element_to_be_clickable(element))
            else:
                self.logger.error(self.caller_name, f"Invalid element type for click: {type(element)}")
                return False

            if target_element:
                target_element.click()
                return True
            else:
                 # Should not happen if wait succeeds, but as a safeguard
                 self.logger.error(self.caller_name, f"Element became None after wait for clickable: {locator_for_msg}")
                 return False

        except TimeoutException:
            self.logger.warn(self.caller_name, f"Timeout waiting for element to be clickable: {locator_for_msg}")
            return False
        except Exception as e:
            self.logger.error(self.caller_name, f"Error clicking element {locator_for_msg}: {e}", exc_info=False)
            return False

    def type(self, element: ElementParam, text: str, clear_first: bool = True, wait_time: int = 10) -> bool:
        """Types text into an element, optionally clearing it first."""
        target_element: Optional[WebElement] = None
        locator_for_msg = 'WebElement provided'

        # Find the element first if a locator is provided
        if isinstance(element, WebElement):
            target_element = element
        elif isinstance(element, tuple) and len(element) == 2:
            locator_for_msg = element
            # Wait for presence first before trying to type
            target_element = self.find_element(element[0], element[1], wait_time)
        else:
             self.logger.error(self.caller_name, f"Invalid element type for type: {type(element)}")
             return False

        if not target_element:
             self.logger.warning(self.caller_name, f"Cannot type, element not found: {locator_for_msg}")
             return False

        # Ensure focus is correct *after* finding the element
        driver = self._ensure_focus_and_get_driver()
        if not driver:
             return False

        try:
            # Wait for the element to be visible before interacting
            # Use the WebElement instance now for visibility check
            WebDriverWait(driver, wait_time).until(EC.visibility_of(target_element))

            if clear_first:
                target_element.clear()
                time.sleep(0.1) # Small pause after clear
            target_element.send_keys(text)
            return True
        except Exception as e:
            self.logger.error(self.caller_name, f"Error typing into element {locator_for_msg}: {e}", exc_info=False)
            return False

    def hover(self, element: ElementParam, wait_time: int = 10) -> bool:
        """Hovers the mouse pointer over an element."""
        target_element: Optional[WebElement] = None
        locator_for_msg = 'WebElement provided'

        if isinstance(element, WebElement):
            target_element = element
        elif isinstance(element, tuple) and len(element) == 2:
            locator_for_msg = element
            # Wait for presence before trying to hover
            target_element = self.find_element(element[0], element[1], wait_time)
        else:
             self.logger.error(self.caller_name, f"Invalid element type for hover: {type(element)}")
             return False

        if not target_element:
             self.logger.warning(self.caller_name, f"Cannot hover, element not found: {locator_for_msg}")
             return False

        driver = self._ensure_focus_and_get_driver()
        if not driver:
            return False

        try:
             # Wait for visibility before hovering? Usually presence is enough.
             # WebDriverWait(driver, wait_time).until(EC.visibility_of(target_element))
            actions = ActionChains(driver)
            actions.move_to_element(target_element).perform()
            return True
        except Exception as e:
            self.logger.error(self.caller_name, f"Error hovering over element {locator_for_msg}: {e}", exc_info=False)
            return False

    def switch_to_iframe(self, iframe_locator: IFrameParam, wait_time: int = 10) -> bool:
        """Switches the driver context into an iframe within this tab."""
        driver = self._ensure_focus_and_get_driver()
        if not driver:
            return False
        try:
            wait = WebDriverWait(driver, wait_time)
            wait.until(EC.frame_to_be_available_and_switch_to_it(iframe_locator))
            # self.logger.debug(self.caller_name, f"Switched into iframe: {iframe_locator}")
            return True
        except TimeoutException:
            self.logger.warning(self.caller_name, f"Timeout waiting for iframe '{iframe_locator}'")
            return False
        except Exception as e:
            self.logger.error(self.caller_name, f"Error switching to iframe '{iframe_locator}': {e}", exc_info=False)
            return False

    def switch_to_default_content(self) -> bool:
        """Switches the driver context back to the main page content."""
        driver = self._ensure_focus_and_get_driver()
        if not driver:
            return False
        try:
            driver.switch_to.default_content()
            # self.logger.debug(self.caller_name, "Switched to default content.")
            return True
        except Exception as e:
            self.logger.error(self.caller_name, f"Error switching to default content: {e}", exc_info=False)
            return False

    def close(self) -> bool:
        """Closes this tab via the browser manager."""
        self.logger.info(self.caller_name, f"Requesting close for tab {self.handle}")
        return self.browser.close_tab(self)

    def is_active(self) -> bool:
        """Checks if this tab is the currently focused tab in the browser."""
        active_handle = self.browser.get_active_tab_handle()
        # Check if active_handle is not None before comparing
        return active_handle is not None and self.handle == active_handle

    # --- Base methods for subclasses to override ---

    def run_scrapper_task(self, *args, **kwargs):
         """Placeholder for specific scraping logic in subclasses."""
         self.logger.warning(self.caller_name, "run_scrapper_task() called on base ChromeTab. Subclass should implement this.")
         # Example: Subclass might navigate, find elements, extract data
         pass
