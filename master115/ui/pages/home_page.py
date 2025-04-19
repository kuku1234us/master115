import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QGroupBox, QApplication
)
from PyQt6.QtCore import Qt

# Framework imports
from qt_base_app.theme import ThemeManager
from qt_base_app.models import SettingsManager, SettingType, Logger

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains

# Add requests import
# import requests

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False


class HomePage(QWidget):
    """
    Acts as the temporary host for the Login Exploration Helper tool.
    Configuration is now managed in PreferencesPage.
    """
    # Keys to access settings saved by PreferencesPage
    CHROME_PATH_KEY = 'exploration/chrome_path'
    DRIVER_PATH_KEY = 'exploration/driver_path'
    USE_WEBDRIVER_MANAGER_KEY = 'exploration/use_webdriver_manager'

    # Default paths (fallback if settings not found)
    DEFAULT_CHROME_PATH = "C:\\Users\\Administrator\\AppData\\Local\\115Chrome\\Application\\115chrome.exe"
    DEFAULT_DRIVER_PATH = "D:\\projects\\chromedriver\\chromedriver.exe"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HomePage")
        self.theme = ThemeManager.instance()
        self.settings = SettingsManager.instance()
        self.logger = Logger.instance()
        self.caller_name = "HomePage"

        self.exploration_driver: Optional[webdriver.Chrome] = None
        self.test_tab_handle: Optional[str] = None # Handle for the explicitly created tab

        self._setup_ui()
        # No _load_paths() needed here anymore

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Control Group ---
        control_group = QGroupBox("Login Exploration Session Control")
        control_layout = QVBoxLayout(control_group)

        self.start_button = QPushButton("Start 115chrome Browser")
        self.start_button.clicked.connect(self._start_browser)

        self.open_test_tab_button = QPushButton("Open Test Tab & Go to Folder")
        self.open_test_tab_button.clicked.connect(self._open_test_tab)
        self.open_test_tab_button.setEnabled(False)

        self.save_source_button = QPushButton("Save Main Page Source")
        self.save_source_button.clicked.connect(self._save_page_source)
        self.save_source_button.setEnabled(False)
        
        self.find_items_button = QPushButton("Find Folder Items (IFrame Content)")
        self.find_items_button.clicked.connect(self._find_folder_items)
        self.find_items_button.setEnabled(False)

        self.trigger_download_button = QPushButton("Trigger Download (Hover+Click)")
        self.trigger_download_button.clicked.connect(self._trigger_download)
        self.trigger_download_button.setEnabled(False)

        self.close_button = QPushButton("Close Browser")
        self.close_button.clicked.connect(self._close_browser)
        self.close_button.setEnabled(False)

        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.open_test_tab_button)
        control_layout.addWidget(self.save_source_button)
        control_layout.addWidget(self.find_items_button)
        control_layout.addWidget(self.trigger_download_button)
        control_layout.addWidget(self.close_button)

        # --- Status Group ---
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        self.status_label = QLabel("Idle - Configure paths in Preferences")
        status_layout.addWidget(self.status_label)

        # --- Add groups to main layout ---
        main_layout.addWidget(control_group)
        main_layout.addWidget(status_group)
        main_layout.addStretch()

        self.setLayout(main_layout)

        # Apply theme background
        bg_color = self.theme.get_color('background', 'content')
        self.setStyleSheet(f"QWidget#HomePage {{ background-color: {bg_color}; }}")

    def _start_browser(self):
        """Starts the Selenium-controlled 115chrome browser using saved settings.
           Does NOT navigate or switch tabs automatically.
        """
        if self.exploration_driver:
            self.logger.warn(self.caller_name, "Exploration browser already running.")
            self.status_label.setText("Browser already running.")
            return

        self.status_label.setText("Starting browser...")
        QApplication.processEvents() # Update UI

        # --- Get settings directly from SettingsManager --- #
        chrome_path = self.settings.get(self.CHROME_PATH_KEY, self.DEFAULT_CHROME_PATH, SettingType.PATH)
        driver_path = self.settings.get(self.DRIVER_PATH_KEY, self.DEFAULT_DRIVER_PATH, SettingType.PATH)
        default_use_wdm = WEBDRIVER_MANAGER_AVAILABLE
        use_wdm = self.settings.get(self.USE_WEBDRIVER_MANAGER_KEY, default_use_wdm, SettingType.BOOL)
        
        # Convert Path objects to strings for validation/use
        chrome_path_str = str(chrome_path) if chrome_path else ""
        driver_path_str = str(driver_path) if driver_path else ""
        # --------------------------------------------------- #

        if not chrome_path_str or not os.path.exists(chrome_path_str):
            self.logger.error(self.caller_name, f"115chrome path is invalid or not set in Preferences: {chrome_path_str}")
            self.status_label.setText("Error: 115chrome path invalid (Set in Preferences)")
            return

        if not use_wdm and (not driver_path_str or not os.path.exists(driver_path_str)):
            self.logger.error(self.caller_name, f"ChromeDriver path is invalid or not set in Preferences: {driver_path_str}")
            self.status_label.setText("Error: ChromeDriver path invalid (Set in Preferences or enable WDM)")
            return

        if use_wdm and not WEBDRIVER_MANAGER_AVAILABLE:
            self.logger.error(self.caller_name, "WebDriver Manager selected in Preferences, but package not found.")
            self.status_label.setText("Error: webdriver-manager package not found (Check Preferences)")
            return

        try:
            options = Options()
            options.binary_location = chrome_path_str
            options.add_argument("--start-maximized")
            
            # --- Add User Data Directory --- #
            user_data_path = r"C:\Users\Administrator\AppData\Local\115Chrome\User Data"
            self.logger.info(self.caller_name, f"Attempting to use User Data Directory: {user_data_path}")
            options.add_argument(f"user-data-dir={user_data_path}")
            # ------------------------------- #

            if use_wdm:
                self.logger.info(self.caller_name, "Using WebDriver Manager (based on Preferences)...")
                service = Service(ChromeDriverManager().install())
            else:
                self.logger.info(self.caller_name, f"Using specified ChromeDriver (based on Preferences): {driver_path_str}")
                service = Service(driver_path_str)

            self.logger.info(self.caller_name, f"Initializing Chrome WebDriver for: {chrome_path_str}")
            self.exploration_driver = webdriver.Chrome(service=service, options=options)
            self.logger.info(self.caller_name, "WebDriver initialized.")

            # --- Browser started successfully --- # 
            self.status_label.setText("Browser Started - Ready for Actions")
            self.start_button.setEnabled(False)
            self.open_test_tab_button.setEnabled(True)
            self.save_source_button.setEnabled(True)
            self.find_items_button.setEnabled(True)
            self.trigger_download_button.setEnabled(True)
            self.close_button.setEnabled(True)

        except Exception as e:
            self.logger.error(self.caller_name, f"Failed to start browser: {e}", exc_info=True)
            self.status_label.setText(f"Error starting browser: {e}")
            if self.exploration_driver:
                 try: self.exploration_driver.quit()
                 except: pass
            self.exploration_driver = None
            self.start_button.setEnabled(True)
            self.open_test_tab_button.setEnabled(False)
            self.save_source_button.setEnabled(False)
            self.find_items_button.setEnabled(False)
            self.trigger_download_button.setEnabled(False)
            self.close_button.setEnabled(False)

    def _open_test_tab(self):
        """Opens a new tab, switches to it, and navigates to the target 115 folder page."""
        if not self.exploration_driver:
            self.logger.warn(self.caller_name, "Open Test Tab requested, but browser is not running.")
            self.status_label.setText("Browser not running.")
            return

        self.status_label.setText("Opening new tab...")
        QApplication.processEvents()

        try:
            self.logger.info(self.caller_name, "Opening and switching to a new tab...")
            # Selenium automatically switches focus when creating a new tab/window
            self.exploration_driver.switch_to.new_window('tab') 
            self.test_tab_handle = self.exploration_driver.current_window_handle
            self.logger.info(self.caller_name, f"Switched to new test tab handle: {self.test_tab_handle}")

            target_url = "https://115.com/?cid=3144897113368821186&offset=0&tab=&mode=wangpan"
            self.logger.info(self.caller_name, f"Attempting navigation in new tab to: {target_url}")
            self.exploration_driver.get(target_url)
            self.logger.info(self.caller_name, f"Navigation to {target_url} in new tab completed.")
            
            self.status_label.setText(f"New tab opened ({self.test_tab_handle}) and navigated to folder URL.")

        except Exception as e:
            self.logger.error(self.caller_name, f"Failed to open or navigate new tab: {e}", exc_info=True)
            self.status_label.setText(f"Error opening new tab: {e}")
            # Reset test tab handle if it failed
            self.test_tab_handle = None 

    def _find_folder_items(self):
        """Switches to the file list iframe and saves its body's innerHTML."""
        if not self.exploration_driver:
            self.logger.warn(self.caller_name, "Find Folder Items requested, but browser is not running.")
            self.status_label.setText("Browser not running.")
            return
            
        self.status_label.setText("Attempting to find items in iframe...")
        QApplication.processEvents()
        
        iframe_name = "wangpan"
        iframe_found = False
        innerHTML = "Error: Could not retrieve iframe content."
        
        try:
            # Wait for the iframe to be available and switch to it
            self.logger.info(self.caller_name, f"Waiting for iframe '{iframe_name}' and switching focus...")
            wait = WebDriverWait(self.exploration_driver, 10) # Wait up to 10 seconds
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, iframe_name)))
            iframe_found = True
            self.logger.info(self.caller_name, f"Successfully switched focus into '{iframe_name}' iframe.")
            
            # Get the innerHTML of the body within the iframe
            self.logger.info(self.caller_name, "Attempting to get iframe body innerHTML...")
            iframe_body = self.exploration_driver.find_element(By.TAG_NAME, 'body')
            innerHTML = iframe_body.get_attribute('innerHTML')
            self.logger.info(self.caller_name, f"Successfully retrieved iframe innerHTML (length: {len(innerHTML)}).")

        except TimeoutException:
            self.logger.error(self.caller_name, f"Timeout waiting for iframe '{iframe_name}' to become available.")
            self.status_label.setText(f"Error: Timed out waiting for iframe '{iframe_name}'.")
            innerHTML = f"Error: Timed out waiting for iframe '{iframe_name}'."
        except NoSuchElementException:
            self.logger.error(self.caller_name, "Could not find <body> tag within the iframe.")
            self.status_label.setText("Error: Cannot find content within iframe.")
            innerHTML = "Error: Cannot find content within iframe."
        except Exception as e:
            self.logger.error(self.caller_name, f"Error accessing iframe content: {e}", exc_info=True)
            self.status_label.setText(f"Error accessing iframe: {e}")
            innerHTML = f"Error accessing iframe: {e}"
        finally:
            # IMPORTANT: Switch back to the default content regardless of success/failure inside iframe
            if iframe_found: # Only switch back if we successfully switched in
                try:
                    self.exploration_driver.switch_to.default_content()
                    self.logger.info(self.caller_name, "Switched focus back to default content.")
                except Exception as e_switch_back:
                     self.logger.error(self.caller_name, f"Error switching back to default content: {e_switch_back}")
                     # This is problematic, might need to restart driver?

        # Save the retrieved content (or error message) to a file
        try:
            repo_dir = Path("./page_repo")
            repo_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = repo_dir / f"iframe_content_{timestamp}.html"

            with open(filename, "w", encoding="utf-8") as f:
                f.write(innerHTML)

            self.logger.info(self.caller_name, f"Iframe content saved to: {filename}")
            if "Error:" not in innerHTML:
                 self.status_label.setText(f"Iframe content saved to {filename.name}")
            # Keep error message if saving failed inside iframe

        except Exception as e_save:
            self.logger.error(self.caller_name, f"Failed to save iframe content to file: {e_save}", exc_info=True)
            self.status_label.setText(f"Error saving iframe content: {e_save}")

    def _trigger_download(self):
        """Finds the first item, hovers over it, and clicks its directory download link."""
        if not self.exploration_driver:
            self.logger.warn(self.caller_name, "Trigger Download requested, but browser is not running.")
            self.status_label.setText("Browser not running.")
            return

        self.status_label.setText("Attempting hover-and-click download for first item...")
        QApplication.processEvents()

        iframe_name = "wangpan"
        iframe_found = False

        try:
            # 1. Switch into the iframe
            self.logger.info(self.caller_name, f"Hover+Click: Waiting for iframe '{iframe_name}'...")
            wait = WebDriverWait(self.exploration_driver, 10)
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, iframe_name)))
            iframe_found = True
            self.logger.info(self.caller_name, f"Hover+Click: Switched into '{iframe_name}' iframe.")

            # 2. Wait for the first list item to be present
            self.logger.info(self.caller_name, "Hover+Click: Waiting for first list item (li[rel='item'])...")
            first_item_selector = (By.CSS_SELECTOR, "li[rel='item']")
            wait_inside_frame = WebDriverWait(self.exploration_driver, 15)
            first_item_li = wait_inside_frame.until(EC.presence_of_element_located(first_item_selector))
            self.logger.info(self.caller_name, "Hover+Click: First list item (li) found.")

            # 3. Hover over the first item to reveal the download button
            self.logger.info(self.caller_name, "Hover+Click: Hovering over the first list item...")
            actions = ActionChains(self.exploration_driver)
            actions.move_to_element(first_item_li).perform()
            time.sleep(0.5) # Brief pause for JS/CSS effects after hover
            self.logger.info(self.caller_name, "Hover+Click: Hover action performed.")

            # 4. Find and click the specific download link within the first item
            #    Targeting the directory download link as per the original successful code
            download_link_selector = (By.CSS_SELECTOR, "a[menu='download_dir_one']")
            self.logger.info(self.caller_name, f"Hover+Click: Waiting for download link ({download_link_selector[1]}) to be clickable...")

            # Search within the first_item element context
            download_link = wait_inside_frame.until(
                EC.element_to_be_clickable(first_item_li.find_element(*download_link_selector))
            )
            self.logger.info(self.caller_name, "Hover+Click: Download link found and clickable. Clicking it...")
            download_link.click()
            self.logger.info(self.caller_name, "Hover+Click: Download link clicked.")
            self.status_label.setText("Download triggered via hover+click.")

        except TimeoutException as e:
            self.logger.error(self.caller_name, f"Hover+Click: Timeout waiting for element: {e}")
            self.status_label.setText("Error: Timeout finding item/download link.")
        except NoSuchElementException as e:
            self.logger.error(self.caller_name, f"Hover+Click: Could not find element: {e}")
            self.status_label.setText("Error: Couldn't find item/download link.")
        except Exception as e:
            self.logger.error(self.caller_name, f"Hover+Click: Error triggering download: {e}", exc_info=True)
            self.status_label.setText(f"Error triggering download: {e}")
        finally:
            # Switch back to default content if we switched into the frame
            if iframe_found:
                try:
                    self.exploration_driver.switch_to.default_content()
                    self.logger.info(self.caller_name, "Hover+Click: Switched focus back to default content.")
                except Exception as e_switch_back:
                    self.logger.error(self.caller_name, f"Hover+Click: Error switching back: {e_switch_back}")

    def _close_browser(self):
        """Closes the Selenium-controlled browser."""
        self.status_label.setText("Closing browser...")
        QApplication.processEvents() # Update UI

        if self.exploration_driver:
            try:
                self.exploration_driver.quit()
                self.logger.info(self.caller_name, "Exploration browser closed successfully.")
            except Exception as e:
                self.logger.error(self.caller_name, f"Error quitting browser: {e}", exc_info=True)
            finally:
                self.exploration_driver = None
                self.test_tab_handle = None # Reset test tab handle
                self.status_label.setText("Browser Closed.")
                self.start_button.setEnabled(True)
                self.open_test_tab_button.setEnabled(False)
                self.save_source_button.setEnabled(False)
                self.find_items_button.setEnabled(False)
                self.trigger_download_button.setEnabled(False)
                self.close_button.setEnabled(False)
        else:
            self.logger.warn(self.caller_name, "Close browser called but no active driver found.")
            self.status_label.setText("Idle (No browser was running).")
            self.start_button.setEnabled(True)
            self.open_test_tab_button.setEnabled(False)
            self.save_source_button.setEnabled(False)
            self.find_items_button.setEnabled(False)
            self.trigger_download_button.setEnabled(False)
            self.close_button.setEnabled(False)

    def _save_page_source(self):
        """Saves the current page source of the driver's *currently focused* tab to ./page_repo/"""
        if not self.exploration_driver:
            self.logger.warn(self.caller_name, "Save page source requested, but browser is not running.")
            self.status_label.setText("Browser not running.")
            return

        try:
            source = self.exploration_driver.page_source
            url = self.exploration_driver.current_url
            self.logger.info(self.caller_name, f"Saving page source for URL: {url}")

            repo_dir = Path("./page_repo")
            repo_dir.mkdir(parents=True, exist_ok=True) # Create directory if needed

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Basic filename cleaning (replace common invalid chars)
            safe_part = url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "-").replace("?", "_").replace("=", "-")
            # Limit length to avoid issues
            max_len = 50
            safe_part = safe_part[:max_len] if len(safe_part) > max_len else safe_part
            
            filename = repo_dir / f"pagesource_{safe_part}_{timestamp}.html"

            with open(filename, "w", encoding="utf-8") as f:
                f.write(source)

            self.logger.info(self.caller_name, f"Page source saved to: {filename}")
            self.status_label.setText(f"Page source saved to {filename.name}")

        except Exception as e:
            self.logger.error(self.caller_name, f"Failed to save page source: {e}", exc_info=True)
            self.status_label.setText(f"Error saving page source: {e}")

    def closeEvent(self, event):
        """Handle widget close event."""
        self._close_browser()
        super().closeEvent(event) 