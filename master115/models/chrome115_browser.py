# master115/models/chrome115_browser.py
from __future__ import annotations # For Type Hinting ChromeTab within the class

from typing import Optional, Type, Dict, TypeVar, TYPE_CHECKING
from pathlib import Path
import time

from selenium import webdriver
# from selenium.webdriver.remote.webelement import WebElement # Not directly used here
from selenium.webdriver.common.by import By # Imported but maybe used by callers?
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException, NoSuchWindowException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.action_chains import ActionChains # Moved to ChromeTab

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

# Framework imports
from qt_base_app.models import SettingsManager, Logger, SettingType

# Type hint for ChromeTab without circular import issues at runtime
if TYPE_CHECKING:
    from .chrome_tab import ChromeTab

# Generic TypeVar for ChromeTab subclasses
T_ChromeTab = TypeVar('T_ChromeTab', bound='ChromeTab')


class Chrome115Browser:
    """
    A singleton class to manage the 115chrome browser instance via Selenium.

    Ensures only one browser instance is controlled, suitable for services
    like 115.com that might restrict multiple simultaneous logins/sessions
    with the same user profile.
    """
    _instance = None
    _initialized = False # Flag to ensure __init__ runs only once

    @classmethod
    def instance(cls) -> 'Chrome115Browser':
        """Gets the singleton instance of the browser manager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """
        Private constructor. Use instance() method for access.
        Initializes browser settings and state ONLY ONCE.
        """
        if Chrome115Browser._initialized:
             return

        self.settings: SettingsManager = SettingsManager.instance()
        self.logger: Logger = Logger.instance()
        self.caller_name = "Chrome115Browser"

        self._driver: Optional[webdriver.Chrome] = None
        self._tabs: Dict[str, ChromeTab] = {} # Maps handle -> ChromeTab instance

        # --- Load configuration from SettingsManager ---
        # Use keys matching PreferencesPage/HomePage experiments
        self._chrome_path_key = 'exploration/chrome_path'
        self._driver_path_key = 'exploration/driver_path'
        self._use_wdm_key = 'exploration/use_webdriver_manager'
        self._user_data_dir_key = 'exploration/user_data_dir' # Assuming a new setting key

        self._chrome_path: Optional[Path] = self.settings.get(
            self._chrome_path_key,
            "C:/Users/Administrator/AppData/Local/115Chrome/Application/115chrome.exe", # Use forward slashes
            SettingType.PATH
        )
        self._driver_path: Optional[Path] = self.settings.get(
            self._driver_path_key,
            None, # No default driver path, rely on WDM or user setting
            SettingType.PATH
        )
        self._use_wdm: bool = self.settings.get(
            self._use_wdm_key,
            WEBDRIVER_MANAGER_AVAILABLE, # Default to WDM if available
            SettingType.BOOL
        )
        # Allow user_data_dir to be empty/None to use default profile
        self._user_data_dir: Optional[str] = self.settings.get(
             self._user_data_dir_key,
             None, # Default to None (Selenium uses a temp profile)
             SettingType.STRING # Stored as string path
        )
        # Example: Hardcode for testing if needed, but prefer settings
        # self._user_data_dir: Optional[str] = r"C:/Users/Administrator/AppData/Local/115Chrome/User Data" # Use forward slashes or raw string

        Chrome115Browser._initialized = True
        self.logger.info(self.caller_name, "Chrome115Browser singleton initialized.")

    # --- Core Lifecycle & Configuration ---

    def start(self) -> bool:
        """Initializes and launches the 115chrome browser instance."""
        if self.is_running():
            self.logger.warn(self.caller_name, "Start called, but browser already running.")
            return True

        self.logger.info(self.caller_name, "Attempting to start 115chrome browser...")

        # Refresh paths from settings in case they changed
        self._chrome_path = self.settings.get(self._chrome_path_key, self._chrome_path, SettingType.PATH)
        self._driver_path = self.settings.get(self._driver_path_key, self._driver_path, SettingType.PATH)
        self._use_wdm = self.settings.get(self._use_wdm_key, self._use_wdm, SettingType.BOOL)
        self._user_data_dir = self.settings.get(self._user_data_dir_key, self._user_data_dir, SettingType.STRING)

        # Validate paths
        chrome_path_str = str(self._chrome_path) if self._chrome_path and self._chrome_path.exists() else None
        driver_path_str = str(self._driver_path) if self._driver_path and self._driver_path.exists() else None

        if not chrome_path_str:
            self.logger.error(self.caller_name, f"Cannot start: 115chrome path is invalid or not found: {self._chrome_path}")
            return False

        if not self._use_wdm and not driver_path_str:
            self.logger.error(self.caller_name, f"Cannot start: ChromeDriver path invalid/not found and WDM disabled: {self._driver_path}")
            return False

        if self._use_wdm and not WEBDRIVER_MANAGER_AVAILABLE:
            self.logger.error(self.caller_name, "Cannot start: WebDriver Manager required but package not found.")
            return False

        try:
            options = Options()
            options.binary_location = chrome_path_str
            options.add_argument("--start-maximized")
            # options.add_argument("--disable-gpu") # Sometimes helps stability
            # options.add_argument("--no-sandbox") # Use with caution if needed
            # options.add_argument("--disable-dev-shm-usage") # Often needed in Linux/Docker
            options.add_experimental_option("excludeSwitches", ["enable-logging"]) # Suppress DevTools listening message

            # Detach option keeps browser open after script exit (for debugging)
            # options.add_experimental_option("detach", True)

            if self._user_data_dir and Path(self._user_data_dir).is_dir():
                 self.logger.info(self.caller_name, f"Using User Data Directory: {self._user_data_dir}")
                 options.add_argument(f"--user-data-dir={self._user_data_dir}") # Note the double hyphen
                 # Add profile directory if needed, often 'Default' or 'Profile 1' etc.
                 # options.add_argument("--profile-directory=Default")
            else:
                 self.logger.info(self.caller_name, "No valid User Data Directory specified. Using default temporary profile.")

            service_args = []
            # service_args = ['--log-level=DEBUG', '--log-path=./chromedriver.log'] # Example service logging

            if self._use_wdm:
                self.logger.info(self.caller_name, "Using WebDriver Manager...")
                # Add service_args here if needed
                service = Service(ChromeDriverManager().install(), service_args=service_args)
            else:
                self.logger.info(self.caller_name, f"Using specified ChromeDriver: {driver_path_str}")
                # Add service_args here if needed
                service = Service(executable_path=driver_path_str, service_args=service_args)

            self.logger.info(self.caller_name, f"Initializing Chrome WebDriver for: {chrome_path_str}")
            self._driver = webdriver.Chrome(service=service, options=options)
            self.logger.info(self.caller_name, "WebDriver initialized successfully.")

            # --- Register initial tab(s) ---
            # Import ChromeTab here locally to avoid circular dependency at module level if needed
            from .chrome_tab import ChromeTab
            initial_handles = self._driver.window_handles
            self._tabs.clear() # Clear any old state
            for handle in initial_handles:
                self._tabs[handle] = ChromeTab(self, handle)
                self.logger.info(self.caller_name, f"Registered initial tab with handle: {handle}")
            # ----------------------------->

            return True

        except WebDriverException as e:
             self.logger.error(self.caller_name, f"WebDriverException starting browser: {e}", exc_info=True)
             if "user data directory is already in use" in str(e).lower():
                  self.logger.error(self.caller_name, "Error suggests another Chrome instance might be using the same profile directory. Close other instances or use a different profile path in settings.")
             self._driver = None
             self._tabs.clear()
             return False
        except Exception as e:
            self.logger.error(self.caller_name, f"Generic Exception starting browser: {e}", exc_info=True)
            self._driver = None
            self._tabs.clear()
            return False

    def quit(self) -> None:
        """Closes all tabs and shuts down the WebDriver process."""
        if not self._driver: # Check _driver directly, is_running() might fail if driver crashed
            self.logger.info(self.caller_name, "Quit called, but browser driver not active.")
            return

        self.logger.info(self.caller_name, "Attempting to quit browser...")
        try:
            self._driver.quit()
            self.logger.info(self.caller_name, "Browser quit successfully.")
        except Exception as e:
            self.logger.error(self.caller_name, f"Exception during browser quit: {e}", exc_info=True)
        finally:
            self._driver = None
            self._tabs.clear()
            self.logger.info(self.caller_name, "Browser state cleared.")


    def is_running(self) -> bool:
        """Checks if the WebDriver instance is active and responsive."""
        if self._driver is None:
            return False
        try:
            # Accessing a property like window_handles forces communication with the driver
            _ = self._driver.window_handles
            return True
        except WebDriverException as e:
            # Specific exceptions indicating the browser/driver is closed or crashed
            if isinstance(e, (NoSuchWindowException, ConnectionRefusedError)) or \
               "browser window is closed" in str(e).lower() or \
               "invalid session id" in str(e).lower() or \
               "target window already closed" in str(e).lower():
                self.logger.warning(self.caller_name, f"is_running check failed: Driver unresponsive or closed ({type(e).__name__}). Cleaning up state.")
                # Attempt cleanup if we detect it's dead
                self._driver = None
                self._tabs.clear()
                return False
            else:
                # Other WebDriver exception might occur, log it but maybe it's recoverable?
                self.logger.error(self.caller_name, f"is_running check encountered WebDriverException: {e}", exc_info=False)
                return False # Assume not running if error occurs
        except Exception as e:
            self.logger.error(self.caller_name, f"is_running check encountered unexpected Exception: {e}", exc_info=True)
            return False # Assume not running


    def get_webdriver(self) -> Optional[webdriver.Chrome]:
        """Provides access to the underlying WebDriver instance if running."""
        if self.is_running():
            return self._driver
        # self.logger.warn(self.caller_name, "Attempted to get WebDriver, but browser is not running.")
        return None

    # --- Tab Management ---

    def open_tab(self, url: Optional[str] = None, tab_class: Type[T_ChromeTab] = None) -> Optional[T_ChromeTab]:
        """Opens a new tab, registers it, and optionally navigates."""
        # Import default ChromeTab locally if tab_class is None
        if tab_class is None:
            from .chrome_tab import ChromeTab
            tab_class = ChromeTab # type: ignore

        if not self.is_running() or not self._driver:
             self.logger.error(self.caller_name, "Cannot open tab, browser not running.")
             return None

        self.logger.info(self.caller_name, f"Opening new tab (type: {tab_class.__name__})...")
        try:
            original_handles = set(self._driver.window_handles)
            self._driver.switch_to.new_window('tab')
            # Wait briefly for the new handle to appear
            time.sleep(0.5)
            current_handles = set(self._driver.window_handles)

            new_handles = current_handles - original_handles
            if not new_handles:
                 # Sometimes the handle might not appear immediately or switch fails
                 self.logger.warning(self.caller_name, "Could not detect new tab handle immediately. Retrying handle detection.")
                 time.sleep(1) # Longer wait
                 current_handles = set(self._driver.window_handles)
                 new_handles = current_handles - original_handles
                 if not new_handles:
                     self.logger.error(self.caller_name, "Failed to identify a unique new tab handle after opening.")
                     # Attempt to close the potentially problematic new window? Focus might be wrong.
                     try: self._driver.close()
                     except: pass
                     return None

            new_handle = list(new_handles)[0] # Get the single new handle
            # Ensure focus is on the new handle, new_window should do this, but be sure
            self._driver.switch_to.window(new_handle)

            # Instantiate the specific Tab class
            # Cast is needed because TypeVar logic isn't fully understood by static checkers here
            new_tab_instance: T_ChromeTab = tab_class(self, new_handle) # type: ignore
            self._tabs[new_handle] = new_tab_instance
            self.logger.info(self.caller_name, f"Registered new tab '{new_handle}' of type {tab_class.__name__}")

            # Navigate if URL provided - delegate to the new tab instance
            if url:
                self.logger.info(self.caller_name, f"Navigating new tab '{new_handle}' to: {url}")
                if not new_tab_instance.navigate(url):
                     self.logger.warning(self.caller_name, f"Navigation failed for new tab '{new_handle}'.")
                     # Decide if we should still return the tab instance or None

            self.logger.info(self.caller_name, f"New tab '{new_handle}' opened successfully.")
            return new_tab_instance

        except Exception as e:
            self.logger.error(self.caller_name, f"Failed to open new tab: {e}", exc_info=True)
            return None


    def close_tab(self, tab_instance: ChromeTab) -> bool:
        """Closes the specified tab."""
        handle = tab_instance.get_handle()
        if not self.is_running() or not self._driver:
             self.logger.error(self.caller_name, f"Cannot close tab '{handle}', browser not running.")
             return False
        if handle not in self._tabs:
            self.logger.warning(self.caller_name, f"Attempted to close unregistered tab handle: {handle}")
            # Try to close it anyway if it exists in driver handles?
            if handle in self._driver.window_handles:
                 try:
                    self._driver.switch_to.window(handle)
                    self._driver.close()
                    self.logger.info(self.caller_name, f"Closed untracked tab '{handle}' found in driver.")
                    return True
                 except Exception as e_untracked:
                    self.logger.error(self.caller_name, f"Failed to close untracked tab '{handle}': {e_untracked}")
                    return False
            return False

        self.logger.info(self.caller_name, f"Closing tab: {handle}...")
        try:
            current_handles_before_close = self._driver.window_handles
            num_handles_before = len(current_handles_before_close)

            if handle == self._driver.current_window_handle:
                self._driver.close()
            else:
                # Switch to the tab THEN close it
                original_handle = self._driver.current_window_handle
                self._driver.switch_to.window(handle)
                self._driver.close()
                # Try switch back to original handle if it wasn't the one closed and still exists
                if original_handle != handle and original_handle in self._driver.window_handles:
                    try: self._driver.switch_to.window(original_handle)
                    except: pass # Ignore error if original handle also closed somehow

            # Remove from our tracking
            del self._tabs[handle]
            self.logger.info(self.caller_name, f"Tab '{handle}' closed and unregistered.")

            # If other tabs remain, ensure focus is on one of them
            # Check handles *after* close might be more reliable
            current_handles_after_close = self._driver.window_handles
            if current_handles_after_close and self._driver.current_window_handle not in current_handles_after_close:
                 try:
                    self._driver.switch_to.window(current_handles_after_close[0])
                    self.logger.info(self.caller_name, f"Switched focus back to tab: {current_handles_after_close[0]}")
                 except Exception as e_switch:
                    self.logger.error(self.caller_name, f"Failed to switch focus after closing tab: {e_switch}", exc_info=True)
            elif not current_handles_after_close and num_handles_before > 0:
                 # If no handles left and we had handles before, browser should have quit
                 self.logger.info(self.caller_name, "Last tab closed. Clearing driver state.")
                 self._driver = None # Assume quit

            return True
        except NoSuchWindowException:
             self.logger.warning(self.caller_name, f"Tab '{handle}' was already closed.")
             if handle in self._tabs: del self._tabs[handle]
             return True # Treat as success if already closed
        except Exception as e:
            self.logger.error(self.caller_name, f"Failed to close tab '{handle}': {e}", exc_info=True)
            if handle in self._tabs: del self._tabs[handle] # Clean up tracking anyway
            return False


    def switch_focus_to(self, tab_instance: ChromeTab) -> bool:
        """Switches the WebDriver focus to the specified tab."""
        handle = tab_instance.get_handle()
        # Use get_webdriver which incorporates is_running
        driver = self.get_webdriver()
        if not driver:
             self.logger.error(self.caller_name, f"Cannot switch focus to '{handle}', browser not running.")
             return False

        try:
            current_handles = driver.window_handles # Get fresh handles
            if handle not in current_handles:
                 self.logger.error(self.caller_name, f"Cannot switch focus, handle '{handle}' not found in current browser tabs {current_handles}.")
                 if handle in self._tabs:
                      self.logger.warning(self.caller_name, f"Removing stale tab handle '{handle}' from tracking.")
                      del self._tabs[handle]
                 return False
            if driver.current_window_handle == handle:
                 return True # Already focused

            # self.logger.debug(self.caller_name, f"Switching focus to tab: {handle}")
            driver.switch_to.window(handle)
            # Verify switch (optional, adds overhead)
            # time.sleep(0.1)
            # return driver.current_window_handle == handle
            return True

        except NoSuchWindowException:
             self.logger.error(self.caller_name, f"Cannot switch focus, handle '{handle}' seems to be closed (NoSuchWindowException).")
             if handle in self._tabs: del self._tabs[handle]
             return False
        except Exception as e:
            self.logger.error(self.caller_name, f"Failed to switch focus to tab '{handle}': {e}", exc_info=True)
            return False


    def list_tabs(self) -> Dict[str, ChromeTab]:
        """Returns the dictionary mapping handles to tracked ChromeTab instances, pruning stale tabs."""
        if self.is_running() and self._driver:
            try:
                current_handles = set(self._driver.window_handles)
                tracked_handles = set(self._tabs.keys())

                stale_handles = tracked_handles - current_handles
                if stale_handles:
                     self.logger.warning(self.caller_name, f"Pruning stale tab handles from tracking: {stale_handles}.")
                     for stale in stale_handles:
                          if stale in self._tabs: # Check existence before deleting
                             del self._tabs[stale]

                # Check for untracked handles (should ideally not happen if open_tab is used)
                new_untracked = current_handles - tracked_handles
                if new_untracked:
                    self.logger.warning(self.caller_name, f"Found untracked tab handles in driver: {new_untracked}. Registering as generic ChromeTab.")
                    # Import ChromeTab locally if needed
                    from .chrome_tab import ChromeTab
                    for untracked in new_untracked:
                        self._tabs[untracked] = ChromeTab(self, untracked)

            except Exception as e:
                 self.logger.error(self.caller_name, f"Error during list_tabs handle pruning: {e}", exc_info=True)
                 # Potentially driver crashed during check, re-check running status
                 if not self.is_running(): self._tabs.clear()


        return self._tabs.copy() # Return a copy

    def get_active_tab_handle(self) -> Optional[str]:
         """Gets the handle of the currently focused tab."""
         driver = self.get_webdriver()
         if driver:
              try:
                   return driver.current_window_handle
              except Exception as e:
                   # Handle cases where the window might be closing or driver crashed
                   self.logger.error(self.caller_name, f"Error getting current window handle: {e}")
                   self.is_running() # Trigger check which might clean up state
                   return None
         return None

    def get_tab_by_handle(self, handle: str) -> Optional[ChromeTab]:
        """Retrieves a tracked ChromeTab instance by its handle."""
        # Optional: Call list_tabs() first to ensure pruning? Could add overhead.
        # self.list_tabs()
        return self._tabs.get(handle)

    # Add other browser-level utility methods if needed
    # E.g., method to clear cookies, manage profiles etc.

