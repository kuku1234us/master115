# Introduction

This app manages movie downloads via the 115chrome browser.

# Project Goal and Workflow

The primary purpose of the MoviePython application is to streamline and automate the entire process of finding, acquiring, and managing movie downloads using the 115.com cloud storage service and its specialized 115chrome browser. It aims to provide a convenient and efficient alternative to traditional local BitTorrent clients, leveraging 115.com's unique cloud-based magnet link downloading feature.

## The Workflow

The envisioned workflow involves several key steps:

1.  **Information Gathering:** The application will scrape various websites on the internet to find relevant information about movies. This includes:
    *   Magnet links (the core identifier for torrents).
    *   Movie posters.
    *   Movie ratings and other metadata.

2.  **Cloud Linking:** Once a desired movie's magnet link is identified, the application will automate the process of adding this link to the user's 115.com account. This triggers 115.com's internal cloud service to download the torrent's content directly to the user's cloud storage, eliminating the need for a BitTorrent client running on the local machine.

3.  **Local Download:** After 115.com completes the download within its cloud, the MoviePython application will automate the 115chrome browser to download the actual movie files from the user's 115 cloud storage to their local computer.

4.  **Convenient Access:** The collected movie information (posters, ratings, download status) will be organized and presented within the application's interface. A key goal is to make this information accessible, potentially via a mobile interface or companion app, allowing the user to browse available movies and initiate the download process remotely and conveniently while on the go.

By automating these steps, MoviePython intends to create a seamless 'search-link-download' experience tailored specifically for the 115.com ecosystem.

# About 115chrome

The 115chrome browser is a crucial component of the workflow facilitated by this application. It is a specialized version, or fork, of the standard Google Chrome browser, specifically tailored to interact seamlessly with the 115.com cloud storage service. Think of it as a custom key designed to unlock the full potential of your 115.com account.

Why is a special browser needed? The 115.com service offers a unique feature: it allows users to add magnet links (commonly used for BitTorrent file sharing) directly within their cloud storage interface. When a magnet link is added, 115.com initiates the download process entirely within its own cloud infrastructure, bypassing the need for a traditional torrent client on your local machine. Once these files (like movies) are downloaded and stored within your 115.com cloud account, the 115chrome browser provides the optimized tools necessary to download them from the cloud to your local Windows computer at high speeds. Standard browsers lack this specific integration.

This application leverages automation (specifically the Selenium library, as demonstrated in `main.py`) to control the 115chrome browser programmatically. By specifying the path to the 115chrome executable, the application can open the browser, potentially navigate to 115.com, log in (if necessary), and interact with the site to manage downloads, all without manual intervention.

# Experiment Stage

Automating web browser interactions, especially complex login sequences, often requires careful preliminary investigation. Before we can build a fully automated process for logging into 115.com using 115chrome, we need to understand the exact steps, identify the HTML elements involved, and account for any timing issues or dynamic content. The `main.py` script successfully demonstrates launching the browser via Selenium, but the login process itself needs manual exploration under controlled conditions.

To facilitate this, we will create a simple temporary GUI tool within the MoviePython application (or as a separate script initially). This "Login Exploration Helper" will launch the 115chrome browser using Selenium, allowing us to manually perform the login while observing the process using browser developer tools.

## Login Exploration Helper Tool Design

This tool will provide a basic interface to configure and launch the Selenium-controlled browser session.

**1. GUI Layout (Conceptual ASCII Art):**

```
+------------------------------------------------------+
| Login Exploration Helper                             |
+------------------------------------------------------+
|                                                      |
| [Configuration Area]                                 |
|   115chrome Path: [ C:\path\to\115chrome.exe ] [Browse...]
|   ChromeDriver Path: [ D:\path\to\chromedriver.exe ] [Browse...]
|   [X] Use WebDriver Manager                         |
|   [ Save Paths ]                                     |
|                                                      |
|------------------------------------------------------|
| [Control Area]                                       |
|   [ Start 115chrome & Navigate to 115.com ]         |
|   [ Close Browser ] (Disabled)                       |
|                                                      |
|------------------------------------------------------|
| [Status Area]                                        |
|   Status: Idle                                       |
|                                                      |
+------------------------------------------------------+
```

**2. Components:**

*   **Configuration Area:** Allows setting the paths for the `115chrome.exe` and optionally the `chromedriver.exe`. A checkbox enables using `webdriver-manager` to handle the ChromeDriver automatically. Paths are saved persistently using the `SettingsManager`.
*   **Control Area:** Buttons to start and stop the Selenium-controlled browser session.
*   **Status Area:** Provides feedback on the current state of the tool (e.g., launching, running, closed, errors).

### What is WebDriver Manager?

When using Selenium to control a web browser like Chrome (or its forks like 115chrome), Selenium doesn't interact with the browser directly. Instead, it communicates through a specific executable called a **WebDriver**. For Chrome, this is `chromedriver.exe`.

**The Challenge:** The version of the WebDriver (`chromedriver.exe`) *must* precisely match the version of the installed Chrome browser (`115chrome.exe` in our case). Browsers update frequently, meaning the required `chromedriver.exe` version also changes often.

Manually managing this involves:
1.  Checking your browser version.
2.  Going to the ChromeDriver download site.
3.  Finding and downloading the matching version.
4.  Placing the executable somewhere on your system.
5.  Updating your script (`main.py` initially did this) to point to the exact path of that downloaded file.

This manual process is tedious, error-prone, and needs repeating whenever the browser updates.

**The Solution: WebDriver Manager**

`webdriver-manager` is a Python library designed to completely automate this process. When you use it in your code (like the option provided in the Preferences page and the helper tool), typically via `Service(ChromeDriverManager().install())`, it automatically performs the following steps:

1.  **Detects Browser Version:** It checks the version of the Chrome/Chromium browser installed on your system (it usually works correctly even for forks like 115chrome).
2.  **Downloads Matching Driver:** It determines the correct `chromedriver.exe` version needed for your detected browser version and downloads it from the official source.
3.  **Caches the Driver:** It saves the downloaded `chromedriver.exe` to a local cache directory (usually within your user profile, like `~/.wdm/drivers/...`), so it doesn't need to download it every time.
4.  **Provides the Path:** It returns the full path to the correct, cached `chromedriver.exe` directly to the Selenium `Service` object.

**Benefits:**
*   **Convenience:** No more manual downloading or path management.
*   **Reliability:** Greatly reduces errors caused by driver/browser version mismatches.
*   **Simplicity:** Keeps your code cleaner, as you don't need hardcoded paths to the driver.

In the context of our application's Preferences, the "Use WebDriver Manager" checkbox provides a choice: enable it for automated convenience (recommended), or disable it if you need to specify an exact, manually downloaded `chromedriver.exe` for specific reasons (e.g., if automatic detection fails for 115chrome, though this is less likely).

## Exploration Process for Login Automation

The following steps outline how to use the helper tool to gather the necessary information for automating the 115.com login:

1.  **Configure Paths:** Launch the helper tool. Set the correct path to your `115chrome.exe` installation. Decide whether to use `webdriver-manager` or specify the `chromedriver.exe` path manually. Click "Save Paths".
2.  **Start Exploration Session:** Click the "Start 115chrome..." button. The application will:
    *   Initialize Selenium WebDriver using the specified paths and options (ensuring `options.binary_location` points to `115chrome.exe`).
    *   Navigate the controlled browser to `https://115.com`.
    *   Update the status label (e.g., "Browser Running (Manual Control)") and enable the "Close Browser" button.
3.  **Manual Login & Observation:** A new 115chrome window will open, controlled by your application. Now, interact **manually** with this browser window to log in:
    *   Perform each step of the login process (clicking buttons, entering username/password, handling CAPTCHAs/2FA).
    *   **Crucially**, use the browser's Developer Tools (usually opened by pressing F12) simultaneously:
        *   **Inspect Elements:** Right-click on login buttons, input fields, checkboxes, etc., and choose "Inspect" or "Inspect Element".
        *   **Identify Locators:** Find reliable ways to uniquely identify each interactive element. Prioritize `id`, then `name`, unique `class` names, robust `xpath`, or specific `css_selector`. Note these locators down carefully.
        *   **Look for Iframes:** Check if login elements are inside an `<iframe>`. If so, you'll need to note the iframe's `id` or `name` to switch Selenium's context (`driver.switch_to.frame(...)`). Remember you'll need to switch back out (`driver.switch_to.default_content()`) afterwards.
        *   **Observe Timing:** Notice if the page needs time to load elements after certain actions. Are elements disabled initially and then become enabled? These observations indicate where explicit waits (`WebDriverWait`, `expected_conditions`) will be necessary in the automation script.
        *   **Note Element States:** Record any specific states needed, e.g., if a checkbox needs to be checked.
4.  **End Exploration Session:** Once logged in successfully within the controlled browser and confident you've noted all necessary locators and timing considerations, return to the *helper tool's GUI* and click the "Close Browser" button. This gracefully terminates the Selenium session (`driver.quit()`).
5.  **Design Automation:** Using the detailed notes gathered in step 3, start designing the automation logic:
    *   Translate each manual step into the corresponding Selenium command (e.g., `find_element(By.ID, '...').click()`, `find_element(By.NAME, '...').send_keys(...)`).
    *   Implement `WebDriverWait` with appropriate `expected_conditions` (e.g., `element_to_be_clickable`, `visibility_of_element_located`) where timing delays were observed.
    *   Add code to switch into and out of iframes if identified during exploration.
    *   Consider potential error conditions (e.g., wrong password, CAPTCHA failed) and how the script might detect and handle them (or at least report them).
6.  **Implement & Test:** Code the login sequence in a dedicated function or class within the main MoviePython application. Test thoroughly, refining locators and waits as needed.

This structured exploration process, aided by the simple GUI tool, significantly increases the chances of building a reliable and robust automated login function for 115.com using 115chrome.
