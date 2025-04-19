# Introduction

This document details the process discovered for programmatically downloading **individual files** from the 115.com cloud drive service, bypassing the need for direct UI simulation like mouse hovers or clicks. Our initial exploration revealed that simply navigating to URLs found in HTML `href` attributes or directly calling certain JavaScript functions often failed due to missing context or incorrect assumptions about the download mechanism.

The key challenge lies in the fact that the download isn't typically triggered by a single, direct link to the file. Instead, the web application uses a multi-step process involving backend API calls to first retrieve a temporary, authorized download URL, and then uses that URL to fetch the actual file content. This tutorial outlines how to replicate this process using Python.

## The Two-Step API Download Process

Successfully downloading an individual file requires interacting with the 115 backend in two distinct stages:

1.  **Requesting the Final Download URL:** Your code first needs to ask the 115 API server for the specific, temporary URL where the file content can be accessed. This involves sending identifying information about the file (`pick_code`) along with proof of your authenticated session (cookies).
2.  **Fetching the File Content:** Once the API provides the final URL, your code makes a second request to *that* specific URL to retrieve the actual file bytes, which can then be saved locally.

Here's a simplified flow:

```ascii
+-----------+     (1) GET /files/download?pickcode=...     +------------------------+
| Your Code | ---------------------------------------------> | 115 API (webapi.115.com) |
|           |     [Requires: Cookies, Headers]             |                          |
+-----------+                                              +------------------------+
     ^                                                            |
     | (2) JSON Response with "file_url"                          |
     |     {                                                         |
     |       "state": true,                                          |
     |       "file_url": "https://cdn<...>.115.com/<...>?<params>",  |
     |       ...                                                     |
     |     }                                                         V
+-----------+ <-----------------------------------------------------+
| Your Code |
|           |   (3) Extract final_url from Response
+-----------+
     |
     |   (4) GET https://cdn<...>.115.com/<...>?<params>
     |       [Requires: Cookies, Headers from same Session]
     V
+-----------+     (5) File Stream (Bytes)                +------------------------+
| Your Code | <------------------------------------------ | 115 CDN / File Server  |
|           |                                              |                          |
+-----------+                                              +------------------------+
     |
     V
+----------------+
| Save File Disk |
+----------------+
```

Let's break down each step.

## Step 1: Obtaining the Final Download URL

**Purpose:** To authenticate your request and ask the 115 API for the actual location (URL) of the file you want to download.

**Endpoint & Method:**

*   **URL:** `https://webapi.115.com/files/download`
*   **Method:** `GET`

**Parameters:**

*   `pickcode` (required): The unique identifier for the specific *file* you want to download. This code can be found as an attribute on the `<li>` element representing the file in the web interface's HTML source.

**Authentication & Context (Crucial):**

This API call will fail without proper authentication and context, mimicking a real browser session. You need to provide:

1.  **Cookies:** The authentication cookies from an active, logged-in 115.com session are essential. The server uses these to verify your identity and permissions.
2.  **Headers:**
    *   `User-Agent`: It's best practice to send a standard browser User-Agent string. The API might reject requests without one.
    *   `Referer`: This header is often critical. Set it to `https://115.com/` to indicate the request originates from the main site context. Omitting or having an incorrect Referer can lead to errors.

**SSL Verification Issue:**

In some Python environments, the default certificate authorities might not recognize the certificate used by `webapi.115.com`. This results in an `SSLCertVerificationError`. For development or internal tools where you trust the endpoint, you can bypass this by adding `verify=False` to your `requests` call. **Note:** Disabling verification reduces security and should be done cautiously.

**Expected Response:**

If successful, the API returns a JSON object. The key piece of information within this JSON is the final download URL, typically found under the key `"file_url"`.

```json
{
  "state": true, 
  "error_msg": "", 
  "errcode": 0, 
  "file_id": "...", 
  "file_name": "your_file.nfo", 
  "file_size": "600", 
  "pick_code": "cn1x13e7is7m3dmne", 
  "file_sha1": "...", 
  "file_url": "https://cdnfhnfile.115.com/12345/ABCDE...?wsiphost=local&Expires=...&screenshot=...&key=...&", 
  // ... other fields ...
}
```

**Code Example (Python `requests`):**

```python
import requests
from pathlib import Path

# Assume 'driver' is your active, logged-in Selenium webdriver.Chrome instance
# Assume 'pick_code' is the string containing the code for the desired file

session = requests.Session()

# --- Step 1: Get Cookies --- 
selenium_cookies = driver.get_cookies()
if not selenium_cookies:
    print("ERROR: Failed to get cookies from Selenium driver.")
    # Handle error appropriately
    exit()

for cookie in selenium_cookies:
    session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
print(f"Copied {len(selenium_cookies)} cookies to requests session.")

# --- Step 2: Define Headers --- 
headers = {
    'User-Agent': driver.execute_script("return navigator.userAgent;"),
    'Referer': 'https://115.com/' # Important!
}
print(f"Using headers: {headers}")

# --- Step 3: Call API to get the final download URL --- 
api_url = "https://webapi.115.com/files/download"
api_params = {"pickcode": pick_code}
final_download_url = None
try:
    print(f"GET {api_url} with params {api_params}")
    response = session.get(
        api_url, 
        params=api_params, 
        headers=headers, 
        timeout=20, 
        verify=False # Bypass SSL check if needed
    )
    response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
    
    data = response.json()
    print(f"API Response: {data}")
    
    final_download_url = data.get('file_url')
    if not final_download_url:
        print(f"ERROR: Key 'file_url' not found in API response: {data}")
    else:
        print(f"Extracted final download URL: {final_download_url}")

except requests.exceptions.RequestException as e:
    print(f"ERROR: API request failed: {e}")
except Exception as e:
    print(f"ERROR: Failed to process API response: {e}")

# --- Proceed to Step 2 only if final_download_url was obtained --- 
# ... see next section ...
```

## Step 2: Downloading the File Content

**Purpose:** To retrieve the actual bytes of the file from the temporary URL provided by the API in Step 1.

**Endpoint & Method:**

*   **URL:** The `file_url` obtained from the Step 1 JSON response.
*   **Method:** `GET`

**Authentication & Context:**

It's crucial to use the *same `requests.Session` object* that made the first API call. This ensures the necessary authentication cookies are sent along with the request to the final download URL (which is often on a different domain like `cdn*.115.com`).

**Streaming the Response:**

For potentially large files, it's essential to download the content in chunks rather than loading the entire file into memory at once. This is achieved using `stream=True` in the `requests.get` call and iterating over the response content using `iter_content()`.

**Saving to File:**

The streamed chunks are written sequentially to a local file.

**Code Example (Python `requests`, continuation):**

```python
# (Continuing from Step 1 code)

if final_download_url:
    # --- Step 4: Download the file from the final URL --- 
    print(f"Starting download from final URL...")
    save_dir = Path("./download_api") # Choose your download directory
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # Attempt to derive filename from URL, otherwise use pick_code
    try:
         potential_filename = Path(final_download_url).name.split('?')[0] 
         if '.' in potential_filename: 
              filename = potential_filename
         else:
              filename = f"{pick_code}.download"
    except Exception:
         filename = f"{pick_code}.download"
    
    save_path = save_dir / filename
    print(f"Saving to {save_path}")
    
    try:
        # Reuse the same session and headers (cookies are handled by session)
        download_headers = headers.copy() 
        with session.get(
            final_download_url, 
            stream=True, 
            headers=download_headers, 
            timeout=90, # Longer timeout for potentially large downloads
            verify=False # Bypass SSL check if needed
        ) as dl_response:
            dl_response.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in dl_response.iter_content(chunk_size=8192): # 8KB chunks
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
        print(f"Successfully downloaded and saved file: {filename}")
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Download request failed: {e}")
    except Exception as e:
        print(f"ERROR: Failed to save downloaded file: {e}")
else:
    print("Skipping file download step as final URL was not obtained.")

session.close() # Good practice to close the session
```

## Important Considerations

*   **Individual Files Only:** This documented process and the `https://webapi.115.com/files/download` endpoint were **only confirmed to work for downloading individual files**. Attempts to use this endpoint with a `pickcode` corresponding to a *folder* resulted in a `410 Gone` error, indicating a different mechanism or endpoint is used for folder downloads (which likely involve server-side zipping).
*   **SSL Verification (`verify=False`):** Remember that disabling SSL verification is a security tradeoff. While necessary in some environments for this specific API, understand the risks involved.
*   **API Stability:** Web APIs can change without notice. This process worked as of the time of writing but may require adjustments if 115 modifies their backend.
*   **Error Handling:** The provided code includes basic error handling, but robust applications should implement more comprehensive checks and retries as needed.

## Conclusion

By replicating the two-step process of first querying the `webapi.115.com/files/download` endpoint with the file's `pickcode` and valid session context (cookies/headers) to obtain a final `file_url`, and then using that URL to stream the file content, we can successfully download individual files programmatically without direct UI manipulation.
