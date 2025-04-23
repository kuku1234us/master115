import os
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.driver_cache import DriverCacheManager # Import Cache Manager

from qt_base_app.models import Logger

# Define the specific directory for the face swap chromedriver
# Use forward slashes for path compatibility
DRIVER_INSTALL_DIR = Path("D:/projects/googlechrome_driver")

def initialize_chrome_driver(headless: bool = False) -> webdriver.Chrome | None:
    """
    Initializes a Selenium Chrome WebDriver instance using webdriver-manager,
    ensuring the driver is installed and managed in a specific directory
    (DRIVER_INSTALL_DIR) separate from other potential Chrome drivers.

    Args:
        headless (bool): Whether to run Chrome in headless mode. Defaults to False.

    Returns:
        webdriver.Chrome | None: An initialized WebDriver instance, or None if initialization fails.
    """
    logger = Logger.instance()
    caller = "initialize_chrome_driver"

    try:
        # Ensure the target directory exists
        DRIVER_INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(caller, f"Ensured driver directory exists: {DRIVER_INSTALL_DIR}")

        # Create a cache manager pointing to the desired path
        cache_manager = DriverCacheManager(root_dir=str(DRIVER_INSTALL_DIR))
        # Initialize ChromeDriverManager with the custom cache manager
        manager = ChromeDriverManager(cache_manager=cache_manager)
        
        logger.info(caller, f"Getting ChromeDriver path from manager (install path: {DRIVER_INSTALL_DIR})...")
        # Install the driver (or get the path if already installed in this location)
        driver_path = manager.install() # Call install() without path argument
        logger.info(caller, f"Using ChromeDriver path: {driver_path}")

        # Create a Service object with the specific driver path
        service = Service(executable_path=driver_path)

        # Configure Chrome options
        options = Options()
        if headless:
            options.add_argument("--headless")
            options.add_argument("--disable-gpu") # Often needed for headless
        options.add_argument("--no-sandbox") # Common requirement in some environments
        options.add_argument("--disable-dev-shm-usage") # Overcomes limited resource problems
        # options.add_argument("--window-size=1920,1080") # Optional: set window size
        # Add any other necessary options here
        
        # Suppress console logs from WebDriver/Chrome if desired
        options.add_experimental_option('excludeSwitches', ['enable-logging'])

        logger.info(caller, f"Initializing Chrome WebDriver with service: {driver_path}")
        # Initialize the WebDriver
        driver = webdriver.Chrome(service=service, options=options)
        logger.info(caller, "Chrome WebDriver initialized successfully.")
        return driver

    except Exception as e:
        logger.error(caller, f"Failed to initialize Chrome WebDriver: {e}", exc_info=True)
        return None

# Example usage (for testing purposes):
if __name__ == '__main__':
    print("Attempting to initialize WebDriver...")
    # Need a dummy logger if running standalone
    class DummyLogger:
        def info(self, caller, msg):
            print(f"[INFO] {caller}: {msg}")
        def error(self, caller, msg, exc_info=False):
            print(f"[ERROR] {caller}: {msg}")
    Logger._instance = DummyLogger() # Replace singleton for test
    
    driver_instance = initialize_chrome_driver(headless=True)
    if driver_instance:
        print("WebDriver initialized successfully.")
        try:
            driver_instance.get("https://www.google.com")
            print(f"Page title: {driver_instance.title}")
        except Exception as e:
            print(f"Error during browser interaction: {e}")
        finally:
            driver_instance.quit()
            print("WebDriver quit.")
    else:
        print("Failed to initialize WebDriver.") 