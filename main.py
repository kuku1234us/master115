from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

def main():
    # Path to your ChromeDriver
    chrome_driver_path = "D:\\projects\\chromedriver\\chromedriver.exe"  # Adjust path as needed

    # Set up Chrome options and specify the path to the 115 browser executable
    options = Options()
    options.binary_location = "C:\\Users\\Administrator\\AppData\\Local\\115Chrome\\Application\\115chrome.exe"  # Path to 115 browser executable
    options.add_argument("--start-maximized")

    # Initialize the WebDriver
    service = Service(chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=options)

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
