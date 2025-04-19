# Programmatic Folder Download from 115.com

> **Warning:** 115.com’s download servers enforce very strict cookie, header and origin‐check policies.  
> You must re‑use the browser’s exact cookies and headers to get past their protections.

---

## 1. Extract the folder’s **pickcode**

Every file/folder row on 115.com carries a `pick_code` attribute. For a folder:

```python
from selenium.webdriver.common.by import By

# … after navigating into the list page and switching into the `wangpan` iframe …
folder_li = driver.find_element(By.CSS_SELECTOR, "li[rel='item'][file_type='0']")
pickcode = folder_li.get_attribute("pick_code")
print("Folder pickcode:", pickcode)
