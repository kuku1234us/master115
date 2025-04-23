# Using Python `requests` to List Directory Contents in 115 (Baidu Pan)

This tutorial shows how to programmatically retrieve the contents of a folder (directory) in your 115 cloud drive account using Python’s `requests` library. We will:

1. **Authenticate** (reuse browser cookies).
    
2. **Discover** the folder listing API endpoint.
    
3. **Call** the API with appropriate parameters.
    
4. **Parse** the JSON response.
    
5. **Handle pagination** if your folder contains many items.
    

---

## 1. Prerequisites

- Python 3.7+
    
- `requests` library: install via
    
    ```bash
    pip install requests
    ```
    
- A **logged‑in** session in Chrome/Selenium or your browser, so you can extract the necessary cookies.
    

---

## 2. Authentication & Cookie Extraction

115 uses cookie‑based sessions for its web API. To authenticate your `requests` calls, you must send the same cookies your browser uses.

### 2.1 Extract cookies from Chrome DevTools

1. Open [https://115.com/](https://115.com/) and log in.
    
2. Press `F12` → **Application** tab → **Cookies** → copy the `name=value;` pairs for all cookies under `https://115.com`.
    
3. Store them in a Python dict:
    
    ```python
    cookies = {
        "sessionid": "XYZ...",
        "UID": "12345678",
        # ... copy all domain cookies
    }
    ```
    

---

## 3. Discovering the Folder Listing Endpoint

In your browser DevTools (**Network** → **XHR**), navigate into any folder in your 115 drive. You will see a request like:

```
GET https://webapi.115.com/files?aid=1&cid=<FOLDER_ID>&natsort=1&offset=0&limit=100
```

- `aid=1` – fixed for “My Drive”.
    
- `cid=<FOLDER_ID>` – the folder ID shown in the URL or element attributes (`li[pick_code]` has `cid`).
    
- `natsort=1` – natural (alphanumeric) sort.
    
- `offset` and `limit` – for pagination (0‑based index).
    

The JSON response contains a field like `data.fileList` or `data.list` with an array of entries.

---

## 4. Sample Python Code

```python
import requests

# 1. Prepare session with cookies + headers
session = requests.Session()
# Paste your cookies here:
cookies = {
    "sessionid": "YOUR_SESSION_ID",
    "UID":     "YOUR_USER_ID",
    # ... other 115.com cookies
}
session.cookies.update(cookies)

headers = {
    "User-Agent": "Mozilla/5.0 ...",
    "Referer":    "https://115.com/",
}
session.headers.update(headers)

# 2. Define folder ID and API URL
folder_id = "417965119134480442"  # replace with your folder's CID
api_url = "https://webapi.115.com/files"

# 3. Build query parameters
params = {
    "aid":     1,
    "cid":     folder_id,
    "natsort": 1,
    "offset":  0,
    "limit":   100,
}

# 4. Send GET request
resp = session.get(api_url, params=params, timeout=15)
resp.raise_for_status()
result = resp.json()

# 5. Parse & print entries
# The exact field may vary: try result['data']['file_list'] or result['data']['list']
entries = result.get('data', {}).get('fileList') or result.get('data', {}).get('list')

print(f"Found {len(entries)} items in folder {folder_id}:")
for item in entries:
    print(f"- {item['file_name']}  (pickcode={item['pick_code']}, type={item['file_type']})")

# 6. Handle pagination (if len(entries)==limit)
#    Simply increase offset by `limit` and repeat until fewer items return.
```

---

## 5. Pagination

If your folder contains more than `limit` items (default 100), repeat steps 4–5 with:

```python
params['offset'] += params['limit']
resp = session.get(api_url, params=params)
# ... parse again
```

until the returned list is empty or smaller than `limit`.

---

## 6. Notes & Troubleshooting

- **Endpoint paths** and **response fields** may change. Always verify via DevTools.
    
- If you get HTTP 4xx or 5xx errors, check:
    
    - **Cookies** – ensure they are fresh and valid.
        
    - **Referer** header – should be `https://115.com/`.
        
    - **Rate limits** – avoid hammering the API.
        
- For **shared** or **public** folders, you may need to include `code=<invite_code>` in `params`.
    

---

# 115 WebAPI Root Folder Response Guide

This document explains the meaning of each field in a single entry of the JSON response returned by the 115 WebAPI when retrieving the contents of the root folder.

---

## Response Structure

The API returns a JSON object with a `data` array. Each element in this array represents either a **folder** or a **file** in your account's root directory. The type is distinguished by the presence of `cid` for folders and `fid` for files, along with related fields.

```json
{
  "data": [
    { /* folder entry */ },
    { /* file entry */ },
    ...
  ]
}
```

---

## Common Fields

These fields can appear in both folder and file entries:

|Field|Type|Description|
|---|---|---|
|`aid`|string|Account ID (always `"1"` for personal accounts).|
|`fuuid`|integer|User ID (unique identifier of the current user).|
|`pc`|string|Pick code: unique token for this item, used in download or share APIs.|
|`score`|integer|Rating score (always `0` unless user-added rating feature is in use).|
|`is_top`|integer|Top‑pinned flag (`1` if the item is pinned, `0` otherwise).|
|`issct`|integer|Section‑sharing flag (rarely used).|
|`sh`|string|Share flag (`0` = private, `1` = publicly shared).|
|`cc`|string|Category code (used in advanced classification; empty if unused).|
|`check_code`|integer|Integrity check code result (typically `0`).|
|`check_msg`|string|Message associated with integrity check (empty if no errors).|
|`fl`|array|File-level attributes array (empty list if unused).|

---

## Folder Entry Fields

Folders have these additional fields:

|Field|Type|Description|
|---|---|---|
|`cid`|string|Folder ID (unique identifier for this folder).|
|`pid`|string|Parent folder ID (`"0"` for root-level).|
|`n`|string|Name of the folder.|
|`ns`|string|Name with special characters preserved (same as `n`).|
|`m`|integer|Item count inside folder (`1` for folders by default, or number of sub‑items).|
|`t`|string|Creation timestamp (UNIX epoch in seconds).|
|`te`|string|Creation timestamp (duplicate of `t`).|
|`tu`|string|Last upload or modification timestamp (UNIX epoch).|
|`tp`|string|Original creation timestamp tracked by server.|
|`to`|string|Last access timestamp (UNIX epoch for last open).|
|`e`|string|File extension placeholder (empty for folders).|
|`p`|integer|Permissions flag (0 = default, 1 = special).|
|`u`|string|URL to the folder thumbnail (empty if none).|
|`fc`|integer|File count if folder contains files (0 if none).|
|`fdes`|integer|Flag for file description enabled (0 = no).|
|`hdf`|integer|Hidden flag (0 = visible).|
|`ispl`|integer|Playlist flag (rarely used).|
|`fvs`|integer|File version stamp (0 if unused).|

---

## File Entry Fields

Files have these additional fields:

|Field|Type|Description|
|---|---|---|
|`fid`|string|File ID (unique identifier for this file).|
|`uid`|integer|Owner user ID (same as `fuuid`).|
|`cid`|string|Containing folder ID ("0" for root).|
|`n`|string|File name, including extension.|
|`s`|integer|File size in bytes.|
|`sta`|integer|Status code (1 = normal, other values indicate errors).|
|`pt`|string|Parent type placeholder (usually "0").|
|`p`|integer|Permissions flag (0 = default).|
|`m`|integer|Media flag (0 = not media, 1 = media file).|
|`t`|string|Display timestamp (human-readable creation date).|
|`te`|string|Creation timestamp (UNIX epoch when file was added).|
|`tp`|string|Original creation timestamp.|
|`tu`|string|Last modification upload timestamp (UNIX epoch).|
|`to`|string/integer|Last access timestamp (0 if never accessed).|
|`d`|integer|Downloadable flag (1 = downloadable).|
|`c`|integer|Collection flag (0 = not in favorites).|
|`sh`|integer|Share flag (0 = private).|
|`e`|string|File extension (empty for auto‑detected).|
|`ico`|string|Icon code (file type, e.g., "pdf", "jpg").|
|`class`|string|File class/category code.|
|`fatr`|string|File attribute flags (unused, always "0").|
|`fdes`|integer|Description enabled (0 = no).|
|`sha`|string|SHA1 checksum of the file.|
|`q`|integer|Quality flag (0 = default).|
|`hdf`|integer|Hidden flag (0 = visible).|
|`et`|integer|Encryption type (0 = none).|
|`epos`|string|Encryption position (unused).|
|`u`|string|URL to file preview or thumbnail (if media).|

---

## Usage Tips

- **Listing Contents**: Use the root folder API endpoint to retrieve this structure and iterate through `data` to distinguish folders vs. files.
    
- **Downloading**:
    
    - **Files**: Use the `pc` (pick code) with the `/files/download` API to get a `file_url`, then download.
        
    - **Folders**: Collect all child `pc` values and use the batch download or folder download API endpoint (e.g., `/folder/download`), passing the list of pick codes.
        

---

_Document generated on 2025-04-19._