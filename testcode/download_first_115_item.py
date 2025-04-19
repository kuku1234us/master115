from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def download_first_115_item(driver, iframe_selector='iframe[src*="115.com"]'):
    # 1) Wait for the 115 iframe to appear and switch into it
    iframe = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, iframe_selector))
    )
    driver.switch_to.frame(iframe)

    # 2) Wait for the first download button to be clickable
    download_btn = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[menu="download_dir_one"]'))
    )

    # 3) Click it to trigger download
    download_btn.click()

    # 4) (Optional) switch back out
    driver.switch_to.default_content()

# ─────────────── Example usage ────────────────
if __name__ == '__main__':
    # Set up Chrome with an automatic download folder
    options = webdriver.ChromeOptions()
    prefs = {
        "download.prompt_for_download": False,
        "download.default_directory": "/path/to/save",
        "profile.default_content_setting_values.automatic_downloads": 1
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)
    driver.get('https://115.com/')             # assume already logged in
    driver.get('https://115.com/?tab=wangpan')  # navigate to your cloud drive

    download_first_115_item(driver)

    # ... wait for the download to finish, then quit
    WebDriverWait(driver, 60).until(lambda d: 
        any(fname.endswith('.zip') for fname in os.listdir('/path/to/save'))
    )
    driver.quit()
