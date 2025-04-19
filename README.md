# Selenium 115 Automation

## Project Overview

The goal of this project is to automate the process of downloading movies and other files from the 115 cloud storage service using Selenium. 115.com offers a high-speed download service for users, but manually navigating and downloading files can be time-consuming. This project aims to automate that process by programmatically controlling the 115-compatible browser, navigating through folders, and initiating downloads.

### Proof of Concept

This project will be developed incrementally. The first stage of the project (Proof of Concept) will demonstrate the ability to:

1. Open the 115 browser.
2. Navigate to `https://115.com`.
3. Retrieve and display the page contents in the console.

This will validate that we can successfully automate interactions with the 115 cloud service using Selenium and Python.

## Project Structure

```plaintext
moviepython/
├── pyproject.toml         # Poetry configuration file for managing dependencies
├── README.md              # Project description and documentation
└── core/
    └── __init__.py        # Main script for running the automation
```

## Requirements

- Python (version 3.8 or higher)
- Poetry (for dependency management)
- Selenium (Python package for web automation)
- ChromeDriver (compatible with your version of the 115 browser or Chrome)

## Installation and Setup

1. Clone the repository.
2. Install dependencies using Poetry:
   ```bash
   poetry install
   ```
3. Download the appropriate version of ChromeDriver and place it in a directory that you can reference in the script (e.g., `C:\chromedriver\chromedriver.exe`).

## Usage

Run the proof of concept script using:

```bash
poetry run python selenium_115_automation/__init__.py
```

This will:

1. Open the 115 browser.
2. Navigate to `115.com`.
3. Retrieve the page contents and print them to the console.

## Future Goals

Once the proof of concept is complete, future stages of the project will include:

- Automating login to the 115 cloud account.
- Navigating through folders to locate specific files or directories.
- Initiating downloads for specific folders.
- Scheduling automated downloads for new files in specific folders.
- Error handling and download monitoring.

## License

This project is open-source and licensed under the MIT License.
