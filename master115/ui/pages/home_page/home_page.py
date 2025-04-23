import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
import time
import json # Added json import

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QGroupBox, QApplication
)
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal

# Framework imports
from qt_base_app.theme import ThemeManager
from qt_base_app.models import SettingsManager, SettingType, Logger

# --- Selenium Imports for Google Chrome Test --- #
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options as ChromeOptions # Alias to avoid conflict if other Options are imported
# from webdriver_manager.chrome import ChromeDriverManager # Import the manager
# from webdriver_manager.core.driver_cache import DriverCacheManager # Import Cache Manager
# ---------------------------------------------- #

# --- Use new Browser/Tab classes --- #
from master115.models.chrome115_browser import Chrome115Browser
from master115.models.chrome_tab import ChromeTab

# --- Selenium imports only needed for By --- #
# from selenium import webdriver # No longer needed directly
# from selenium.webdriver.chrome.service import Service # No longer needed directly
# from selenium.webdriver.chrome.options import Options # No longer needed directly
# from selenium.webdriver.support.ui import WebDriverWait # Handled by ChromeTab
# from selenium.webdriver.support import expected_conditions as EC # Handled by ChromeTab
from selenium.webdriver.common.by import By # Keep for specifying locators
from selenium.common.exceptions import TimeoutException, NoSuchElementException # Keep for potential specific error handling
# from selenium.webdriver.common.action_chains import ActionChains # Handled by ChromeTab
# ------------------------------------ #

# --- Import the WebDriver utility function --- #
from master115.models.webdriver_utils import initialize_chrome_driver

# --- Add BrowserButton Import --- #
from .browser_button import BrowserButton, BrowserButtonState
# -------------------------------- #

# --- REMOVE Worker Class --- #
# class BrowserWorker(QObject): ... # Logic moved to MainWindow
# --------------------------- #

# --- REMOVE BrowserWorker Import --- #
# from .home_page import BrowserWorker # Imported in MainWindow now
# ----------------------------------- #

class HomePage(QWidget):
    """
    Acts as the temporary host for the Login Exploration Helper tool.
    Configuration is now managed in PreferencesPage and used by Chrome115Browser.
    This page now interacts with the Chrome115Browser singleton.
    Browser control is delegated to the parent MainWindow.
    """
    # Keep setting keys just for reference if needed, but loading happens in Browser class
    # CHROME_PATH_KEY = 'exploration/chrome_path'
    # DRIVER_PATH_KEY = 'exploration/driver_path'
    # USE_WEBDRIVER_MANAGER_KEY = 'exploration/use_webdriver_manager'

    # Default paths are now handled within Chrome115Browser __init__ as fallbacks
    # DEFAULT_CHROME_PATH = "C:\\Users\\Administrator\\AppData\\Local\\115Chrome\\Application\\115chrome.exe"
    # DEFAULT_DRIVER_PATH = "D:\\projects\\chromedriver\\chromedriver.exe"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HomePage")
        self.theme = ThemeManager.instance()
        # self.settings = SettingsManager.instance() # Browser gets settings now
        self.logger = Logger.instance()
        self.caller_name = "HomePage"
        # self.browser = Chrome115Browser.instance() # Access via parent now

        # --- REMOVE Threading related attributes --- #
        # self.worker_thread: Optional[QThread] = None
        # self.browser_worker: Optional[BrowserWorker] = None
        # self.is_starting: bool = False
        # ------------------------------------------ #

        # self.exploration_driver: Optional[webdriver.Chrome] = None # Replaced by self.browser
        self.test_tab_instance: Optional[ChromeTab] = None # Handle for the explicitly created tab

        self._setup_ui()
        self._update_button_states() # Initial state check (will use parent state)

    # --- Add Helper function for formatting size --- #
    def _format_size(self, size_bytes):
        """Converts bytes to a human-readable string (KB, MB, GB)."""
        if size_bytes is None:
            return "N/A"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes/1024**2:.1f} MB"
        else:
            return f"{size_bytes/1024**3:.1f} GB"
    # --------------------------------------------- #

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Control Group --- #
        control_group = QGroupBox("Login Exploration Session Control")
        control_layout = QVBoxLayout(control_group)

        # --- Replace QPushButton with BrowserButton --- #
        self.browser_button = BrowserButton(self)
        # self.start_button = QPushButton("Start 115chrome Browser") # Text will change
        # self.start_button.setToolTip("Starts the browser using settings from Preferences.")
        # self.start_button.setCheckable(True) # Make it checkable to manage state easily
        # self.start_button.toggled.connect(self._handle_start_stop_click)
        # self.start_button.clicked.connect(self._start_browser) # Replaced by toggled
        # ---------------------------------------------- #

        self.open_test_tab_button = QPushButton("Open Test Tab & Go to Folder")
        self.open_test_tab_button.setToolTip("Opens a new tab and navigates to the sample 115 folder URL.")
        self.open_test_tab_button.clicked.connect(self._open_test_tab)
        # self.open_test_tab_button.setEnabled(False) # Initial state set by _update_button_states

        self.save_source_button = QPushButton("Save Active Tab Source")
        self.save_source_button.setToolTip("Saves the HTML source of the currently focused browser tab.")
        self.save_source_button.clicked.connect(self._save_page_source)
        # self.save_source_button.setEnabled(False)

        self.find_items_button = QPushButton("Save IFrame Content (Active Tab)")
        self.find_items_button.setToolTip("Attempts to find the 'wangpan' iframe in the active tab and saves its content.")
        self.find_items_button.clicked.connect(self._find_folder_items)
        # self.find_items_button.setEnabled(False)

        self.trigger_download_button = QPushButton("Trigger Download (Active Tab)")
        self.trigger_download_button.setToolTip("Attempts hover+click download on the first item in the 'wangpan' iframe of the active tab.")
        self.trigger_download_button.clicked.connect(self._trigger_download)
        # self.trigger_download_button.setEnabled(False)

        # --- Add Get Root Folder Button --- #
        self.get_root_button = QPushButton("Get Root Folder (API)")
        self.get_root_button.setToolTip("Uses browser cookies to fetch root folder contents via 115 API.")
        self.get_root_button.clicked.connect(self._get_root_folder_via_api)
        # -------------------------------- #

        # --- Add View Downloads Button --- #
        self.view_downloads_button = QPushButton("View Downloads Page")
        self.view_downloads_button.setToolTip("Opens 'chrome://downloads' in a new tab and saves its source.")
        self.view_downloads_button.clicked.connect(self._view_downloads_page)
        # ---------------------------------- #

        # --- Temp Google Chrome Test Button --- #
        self.google_chrome_test_button = QPushButton("Google Chrome Test")
        self.google_chrome_test_button.setToolTip("Launches system Chrome, navigates to Baidu, then closes.")
        self.google_chrome_test_button.clicked.connect(self._handle_google_chrome_test)
        # -------------------------------------- #

        # --- Add the new BrowserButton to layout --- #
        control_layout.addWidget(self.browser_button)
        # ------------------------------------------- #
        control_layout.addWidget(self.open_test_tab_button)
        control_layout.addWidget(self.save_source_button)
        control_layout.addWidget(self.find_items_button)
        control_layout.addWidget(self.trigger_download_button)
        # --- Add new button to layout --- #
        control_layout.addWidget(self.get_root_button)
        # -------------------------------- #
        # --- Add view downloads button to layout --- #
        control_layout.addWidget(self.view_downloads_button)
        # ----------------------------------------- #
        # --- Add Google Chrome Test button to layout --- #
        control_layout.addWidget(self.google_chrome_test_button)
        # --------------------------------------------- #
        # control_layout.addWidget(self.quit_button) # Removed

        # --- Status Group --- #
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        self.status_label = QLabel("Idle - Browser not started.")
        status_layout.addWidget(self.status_label)

        # --- Add groups to main layout --- #
        main_layout.addWidget(control_group)
        main_layout.addWidget(status_group)
        main_layout.addStretch()

        self.setLayout(main_layout)

        # Apply theme background
        bg_color = self.theme.get_color('background', 'content')
        self.setStyleSheet(f"QWidget#HomePage {{ background-color: {bg_color}; }}")

        # --- Connect BrowserButton Signals to MainWindow Methods --- #
        main_window = self.parent() # Get the parent MainWindow instance
        # REMOVE isinstance check to avoid circular import NameError
        if main_window: # Ensure parent exists
             # Assume parent has these methods (duck typing)
             try:
                 self.browser_button.start_requested.connect(main_window.start_browser)
                 self.browser_button.cancel_requested.connect(main_window.stop_browser_start)
                 self.browser_button.quit_requested.connect(main_window.quit_browser)
             except AttributeError:
                 self.logger.error(self.caller_name, "Could not connect BrowserButton signals: Parent missing required methods (start_browser, stop_browser_start, quit_browser).")
                 self.browser_button.setEnabled(False)
        else:
            self.logger.error(self.caller_name, "Could not connect BrowserButton signals: Parent does not exist.")
            self.browser_button.setEnabled(False) # Disable if cannot connect
        # ---------------------------------------------------------- #

    def _update_button_states(self, is_starting: bool = False, is_running: bool = False):
        """Updates the BrowserButton state and enables/disables other buttons based on MainWindow state."""
        # Get browser instance safely from parent
        browser = self.parent().browser if hasattr(self.parent(), 'browser') else None
        # is_running = browser.is_running() if browser else False # State passed directly
        new_button_state = BrowserButtonState.IDLE # Default

        # Determine BrowserButton state based on passed arguments
        if is_starting:
            new_button_state = BrowserButtonState.STARTING
            self.status_label.setText("Starting browser...")
        elif is_running:
            new_button_state = BrowserButtonState.RUNNING
            self.status_label.setText("Browser Running - Ready for Actions")
        else: # Not starting and not running (Idle)
            new_button_state = BrowserButtonState.IDLE
            self.status_label.setText("Idle - Browser not started.")
            self.test_tab_instance = None # Clear test tab when browser stopped

        # Set the BrowserButton state
        self.browser_button.set_state(new_button_state)

        # Enable/disable other buttons based on state
        can_interact_with_tabs = is_running and not is_starting
        self.open_test_tab_button.setEnabled(can_interact_with_tabs)
        self.save_source_button.setEnabled(can_interact_with_tabs)
        self.find_items_button.setEnabled(can_interact_with_tabs)
        self.trigger_download_button.setEnabled(can_interact_with_tabs)
        self.get_root_button.setEnabled(can_interact_with_tabs)
        self.view_downloads_button.setEnabled(can_interact_with_tabs)

        # Old logic removed

    def _get_browser_instance(self) -> Optional[Chrome115Browser]:
         """Safely gets the browser instance from the parent MainWindow."""
         if hasattr(self.parent(), 'browser'):
              return self.parent().browser
         self.logger.error(self.caller_name, "Cannot access browser instance from parent.")
         return None

    def _open_test_tab(self):
        """Opens a new tab via MainWindow's browser instance and navigates it."""
        browser = self._get_browser_instance()
        if not browser or not browser.is_running(): # Check parent's browser
            self.logger.warn(self.caller_name, "Open Test Tab requested, but browser is not running.")
            self.status_label.setText("Browser not running. Start it first.")
            # No need to call _update_button_states here, MainWindow handles it
            return

        self.status_label.setText("Opening new test tab...")
        QApplication.processEvents()

        target_url = "https://115.com/?cid=3144897113368821186&offset=0&tab=&mode=wangpan"
        new_tab = browser.open_tab(url=target_url, tab_class=ChromeTab)

        if new_tab:
            self.test_tab_instance = new_tab
            handle = new_tab.get_handle()
            self.logger.info(self.caller_name, f"Successfully opened and navigated test tab: {handle}")
            self.status_label.setText(f"Test tab opened ({handle[-6:]}) and navigated.")
        else:
            self.logger.error(self.caller_name, "Failed to open or navigate new test tab.")
            self.status_label.setText("Error opening new test tab (check logs).")
            self.test_tab_instance = None

        # No need to call _update_button_states here

    def _get_active_tab(self) -> Optional[ChromeTab]:
        """Helper to get the currently focused ChromeTab instance from MainWindow's browser."""
        browser = self._get_browser_instance()
        if not browser or not browser.is_running():
             return None
        active_handle = browser.get_active_tab_handle()
        if not active_handle:
             return None
        tab_instance = browser.get_tab_by_handle(active_handle)
        return tab_instance

    # --- Update methods using _get_browser_instance() and _get_active_tab() --- #

    def _find_folder_items(self):
        """Switches to iframe in active tab, gets source, saves it."""
        active_tab = self._get_active_tab()
        if not active_tab: # Also implicitly checks browser running state via _get_active_tab
            self.logger.warn(self.caller_name, "Find Folder Items requested, but no active tab found or browser not running.")
            self.status_label.setText("Browser not running or no active tab.")
            return

        self.status_label.setText(f"Finding items in iframe (Tab: {active_tab.get_handle()[-6:]})...")
        QApplication.processEvents()

        iframe_name = "wangpan"
        iframe_source: Optional[str] = None
        success = False

        # --- Use ChromeTab methods --- #
        if active_tab.switch_to_iframe(iframe_name):
            self.logger.info(self.caller_name, f"Successfully switched into '{iframe_name}' iframe.")
            iframe_source = active_tab.get_source()
            if iframe_source:
                 self.logger.info(self.caller_name, f"Successfully retrieved iframe innerHTML (length: {len(iframe_source)})." )
                 success = True # Got the source
            else:
                 self.logger.error(self.caller_name, "Failed to get source from within iframe.")

            # Switch back regardless of success getting source
            if not active_tab.switch_to_default_content():
                self.logger.error(self.caller_name, "Critical: Failed to switch back from iframe!")
                # This might require browser restart
        else:
            self.logger.error(self.caller_name, f"Failed to switch into iframe '{iframe_name}'.")
        # -------------------------- #

        # Save the retrieved content (or error message) to a file
        if success and iframe_source is not None:
            try:
                repo_dir = Path("./page_repo")
                repo_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = repo_dir / f"iframe_content_{active_tab.get_handle()[-6:]}_{timestamp}.html"

                with open(filename, "w", encoding="utf-8") as f:
                    f.write(iframe_source)

                self.logger.info(self.caller_name, f"Iframe content saved to: {filename}")
                self.status_label.setText(f"Iframe content saved to {filename.name}")

            except Exception as e_save:
                self.logger.error(self.caller_name, f"Failed to save iframe content to file: {e_save}", exc_info=True)
                self.status_label.setText(f"Error saving iframe content: {e_save}")
        elif not success:
            self.status_label.setText("Error accessing iframe content (check logs)." )
        # else: iframe_source was None, error already logged

        self._update_button_states()

    def _trigger_download(self):
        """Finds first item in active tab's iframe, hovers, clicks download link."""
        active_tab = self._get_active_tab()
        if not active_tab:
            self.logger.warn(self.caller_name, "Trigger Download requested, but no active tab found or browser not running.")
            self.status_label.setText("Browser not running or no active tab.")
            return

        self.status_label.setText(f"Attempting download (Tab: {active_tab.get_handle()[-6:]})...")
        QApplication.processEvents()

        iframe_name = "wangpan"
        download_triggered = False

        # --- Use ChromeTab methods --- #
        if active_tab.switch_to_iframe(iframe_name):
            self.logger.info(self.caller_name, "Hover+Click: Switched into iframe.")
            
            # Find first list item
            first_item_locator = (By.CSS_SELECTOR, "li[rel='item']")
            first_item_li = active_tab.find_element(*first_item_locator, wait_time=15)
            
            if first_item_li:
                 self.logger.info(self.caller_name, "Hover+Click: Found first list item.")
                 # Hover over it
                 if active_tab.hover(first_item_li):
                      self.logger.info(self.caller_name, "Hover+Click: Hover succeeded. Waiting for link...")
                      time.sleep(0.5) # Pause for effects
                      
                      # Find the specific download link within the hovered item
                      # We need to search relative to first_item_li. Selenium doesn't directly
                      # support waiting on sub-elements easily via the base find_element.
                      # Workaround: find the link using the full path after hover.
                      download_link_locator = (By.CSS_SELECTOR, "li[rel='item'] a[menu='download_dir_one']")
                      
                      # Use click method which waits for clickable
                      if active_tab.click(download_link_locator, wait_time=10):
                           self.logger.info(self.caller_name, "Hover+Click: Download link clicked.")
                           download_triggered = True
                      else:
                           self.logger.error(self.caller_name, "Hover+Click: Failed to find or click download link after hover.")
                 else:
                      self.logger.error(self.caller_name, "Hover+Click: Failed to hover over item.")
            else:
                 self.logger.error(self.caller_name, "Hover+Click: Could not find first list item.")

            # Switch back out
            if not active_tab.switch_to_default_content():
                self.logger.error(self.caller_name, "Critical: Failed to switch back from iframe after download attempt!")
        else:
             self.logger.error(self.caller_name, f"Hover+Click: Failed to switch into iframe '{iframe_name}'.")
        # -------------------------- #

        if download_triggered:
            self.status_label.setText("Download likely triggered (check browser)." )
        else:
            self.status_label.setText("Error triggering download (check logs)." )

        self._update_button_states()

    def _save_page_source(self):
        """Saves the current page source of the active tab via ChromeTab."""
        active_tab = self._get_active_tab()
        if not active_tab:
            self.logger.warn(self.caller_name, "Save page source requested, but no active tab found or browser not running.")
            self.status_label.setText("Browser not running or no active tab.")
            return

        self.status_label.setText(f"Saving source (Tab: {active_tab.get_handle()[-6:]})...")
        QApplication.processEvents()

        # --- Delegate to ChromeTab --- #
        saved_path = active_tab.save_source(directory="./page_repo") # Use default directory
        # --------------------------- #

        if saved_path:
            self.status_label.setText(f"Page source saved to {saved_path.name}")
        else:
            self.status_label.setText(f"Error saving page source (check logs)." )
        
        self._update_button_states()

    def _get_root_folder_via_api(self):
        """Calls the browser method to get root folder contents via API."""
        browser = self._get_browser_instance()
        if not browser or not browser.is_running():
            self.logger.warn(self.caller_name, "Get Root Folder API requested, but browser not running.")
            self.status_label.setText("Browser not running. Start it first.")
            return

        self.status_label.setText("Requesting root folder contents via API...")
        QApplication.processEvents()

        folder_data = browser.get_folder_contents_api(folder_id="0") # Assuming 0 is root

        # --- Save Raw JSON Response --- #
        if folder_data is not None:
            try:
                repo_dir = Path("./page_repo")
                repo_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = repo_dir / f"api_response_root_{timestamp}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(folder_data, f, ensure_ascii=False, indent=4)
                self.logger.info(self.caller_name, f"Raw API JSON response saved to: {filename}")
            except Exception as e_save:
                self.logger.error(self.caller_name, f"Failed to save raw API JSON response: {e_save}", exc_info=True)
        # ----------------------------- #

        if folder_data:
            items = None # Initialize items to None
            data_content = folder_data.get('data')

            if isinstance(data_content, list):
                # Case 1: Structure is {'data': [...]} - list is directly under 'data'
                items = data_content
                self.logger.debug(self.caller_name, "API response structure: {'data': [list]}")
            elif isinstance(data_content, dict):
                # Case 2: Structure is {'data': {'list': [...]}} or {'data': {'fileList': [...]}}
                self.logger.debug(self.caller_name, "API response structure: {'data': {dict}}")
                items = data_content.get('list') or data_content.get('fileList')
            else:
                # Case 3: Unexpected structure or 'data' key missing/not list/dict
                self.logger.warning(self.caller_name, f"Unexpected structure for 'data' key in API response: {type(data_content)}. Full response keys: {list(folder_data.keys())}")
                # Optional: Check if list is at top level?
                items = folder_data.get('list') or folder_data.get('fileList')
                if items:
                    self.logger.debug(self.caller_name, "Found item list at the top level of the response.")

            # Try parsing common list keys
            if items is not None: # Check if we successfully extracted a list
                self.logger.info(self.caller_name, f"--- Root Folder Contents (API) ---")
                if not items:
                    self.logger.info(self.caller_name, "(Folder is empty)")
                else:
                    self.logger.info(self.caller_name, f"Found {len(items)} items:")
                    for item in items:
                        # --- Updated Logic based on JSON/Docs --- #
                        is_file = 'fid' in item # Files have 'fid', folders have 'cid'
                        name = item.get('n', '<No Name>')
                        pick_code = item.get('pc', '<No Code>')

                        if is_file:
                            item_type = "File"
                            size_bytes = item.get('s')
                            formatted_size = self._format_size(size_bytes) # Use helper
                            self.logger.info(self.caller_name, f"- [{item_type}] {name} (Size: {formatted_size}, PickCode: {pick_code})")
                        else:
                            item_type = "Dir " # Add space for alignment
                            self.logger.info(self.caller_name, f"- [{item_type}] {name} (PickCode: {pick_code})")
                        # --------------------------------------- #
                self.status_label.setText(f"Root folder contents logged ({len(items)} items).")
            else:
                self.logger.error(self.caller_name, "Could not find item list ('list' or 'fileList') in API response data.")
                self.logger.debug(self.caller_name, f"API Response Data: {folder_data.get('data')}")
                self.status_label.setText("Error parsing folder contents (check logs).")
        else:
             self.status_label.setText("Failed to get root folder contents via API (check logs).")

        self._update_button_states()
    # --------------------------------- #

    def _view_downloads_page(self):
        """Opens chrome://downloads and saves its source."""
        browser = self._get_browser_instance()
        if not browser or not browser.is_running():
            self.logger.warn(self.caller_name, "View Downloads requested, but browser not running.")
            self.status_label.setText("Browser not running. Start it first.")
            return

        self.status_label.setText("Opening chrome://downloads...")
        QApplication.processEvents()

        downloads_tab = browser.open_tab(url="chrome://downloads", tab_class=ChromeTab)

        if not downloads_tab:
            self.logger.error(self.caller_name, "Failed to open chrome://downloads tab.")
            self.status_label.setText("Error opening downloads tab (check logs).")
            self._update_button_states()
            return

        self.logger.info(self.caller_name, f"Opened chrome://downloads tab: {downloads_tab.get_handle()}")
        self.status_label.setText("Saving downloads page source...")
        QApplication.processEvents()

        # Give the page a moment to load internal content (might be needed for chrome:// pages)
        time.sleep(1) 

        saved_path = downloads_tab.save_source(directory="./page_repo", filename_prefix="downloads_page")

        if saved_path:
            self.logger.info(self.caller_name, f"Downloads page source saved to: {saved_path}")
            self.status_label.setText(f"Downloads page source saved to {saved_path.name}")
        else:
            self.logger.error(self.caller_name, "Failed to save downloads page source.")
            self.status_label.setText("Error saving downloads page source (check logs).")

        self._update_button_states()
    # -------------------------------------- #

    # --- Temporary Google Chrome Test Handler --- #
    def _handle_google_chrome_test(self):
        """Launches system Chrome via specified driver, navigates, waits, quits."""
        self.logger.info(self.caller_name, "Starting Google Chrome test...")
        self.status_label.setText("Starting Google Chrome test...")
        QApplication.processEvents()

        # --- Remove local driver setup --- #
        # driver_path = "D:\\projects\\googlechrome_driver\\chromedriver.exe"
        driver = None # Initialize to None

        try:
            # Call the utility function to get the driver
            driver = initialize_chrome_driver(headless=False) # Run non-headless for test

            if not driver:
                # Error logged by utility function
                self.status_label.setText("Error: Failed to initialize Google Chrome driver.")
                return

            self.logger.info(self.caller_name, "Navigating to baidu.com...")
            driver.get("https://www.baidu.com")

            # Check title (basic verification)
            if "百度一下" in driver.title:
                self.logger.info(self.caller_name, f"Successfully navigated to Baidu. Title: {driver.title}")
                self.status_label.setText("Google Chrome test: Navigated to Baidu. Closing soon...")
            else:
                self.logger.warn(self.caller_name, f"Navigation complete but title unexpected: {driver.title}")
                self.status_label.setText("Google Chrome test: Navigation complete, title mismatch. Closing soon...")

            QApplication.processEvents()
            time.sleep(5) # Keep open for 5 seconds

        except Exception as e:
            self.logger.error(self.caller_name, f"Error during Google Chrome test: {e}", exc_info=True)
            self.status_label.setText(f"Error during Google Chrome test: {e}")
        finally:
            if driver:
                self.logger.info(self.caller_name, "Closing Google Chrome test browser.")
                driver.quit()
                self.status_label.setText("Google Chrome test finished and browser closed.")
            else:
                self.logger.info(self.caller_name, "Google Chrome test finished (driver was not initialized).")

        self._update_button_states() # Refresh UI state potentially
    # ------------------------------------------- # 