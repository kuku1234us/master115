from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

def main():
    # Set up Chrome options and specify the path to the 115 browser executable
    options = Options()
    options.binary_location = "C:\\Users\\Administrator\\AppData\\Local\\115Chrome\\Application\\115chrome.exe"  # Path to 115 browser executable
    options.add_argument("--start-maximized")

    # Initialize the WebDriver using ChromeDriverManager
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        # Open the website
        driver.get("https://115.com")

        # Wait for page to load (adjust if needed)
        driver.implicitly_wait(5)

        # Get and print page contents
        page_content = driver.page_source
        print(page_content)

    finally:
        # Close the browser
        driver.quit()

if __name__ == "__main__":
    main()
