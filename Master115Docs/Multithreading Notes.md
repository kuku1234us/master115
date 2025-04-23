# Face‑Swap Automation & Worker‑Thread Notes

*Last updated: 23 Apr 2025*

---

## 1  Automating PixNova uploads with Selenium + 115chrome

```python
from selenium import webdriver, By, EC, WebDriverWait
from pathlib import Path

SRC  = Path(r"C:\swap\source.jpg")
FACE = Path(r"C:\swap\face.jpg")

opt = webdriver.ChromeOptions()
opt.binary_location = r"C:\Program Files\115Chrome\115chrome.exe"
driver = webdriver.Chrome(options=opt)

driver.get("https://pixnova.ai/ai-face-swap/")

wait = WebDriverWait(driver, 60)

# upload hidden <input type=file> fields
wait.until(EC.presence_of_element_located(
    (By.CSS_SELECTOR, "#sourceImage input[type='file']"))).send_keys(str(SRC))

wait.until(EC.presence_of_element_located(
    (By.CSS_SELECTOR, "#faceImage  input[type='file']"))).send_keys(str(FACE))

# click the enabled button inside photo‑pane only
start = wait.until(EC.element_to_be_clickable(
    (By.XPATH, "//div[@id='pane-1']//button"
               "[.//span[normalize-space()='Start face swapping']]")))
start.click()
```

**Why the XPath matters** – Two buttons share that label; restricting the
search to `#pane-1` skips the permanently disabled one.

---

## 2  Waiting for uploads & job completion

| Stage | Selenium wait condition |
|-------|-------------------------|
| Source photo uploaded | `#sourceImage .el-avatar img` visible |
| Face photo uploaded   | `#faceImage  .el-avatar img` visible |
| Swap running          | `.operate-container .loading-container` visible |
| Swap done             | same element becomes invisible |

---

## 3  Download the high‑res result without clicking

1. **Thumbnail URL in DOM**  
   `https://art-global.yimeta.ai/face-swap/<UUID>.webp`

2. **Button’s real request** (seen in DevTools → Network)  
   `https://art-global.yimeta.ai/face-swap/<UUID>.webp?x-oss-process=image/quality,q_99/format,jpg&attname=face-swap.jpg`

```python
thumb = driver.find_element(By.CSS_SELECTOR,
            ".result-container img").get_attribute("src")
uuid  = thumb.rsplit('.', 1)[0]          # strip ".webp"
hires = (uuid + ".webp?x-oss-process=image/quality,q_100/format,jpg"
         "&attname=face-swap.jpg")
```

A regular `requests.get(hires, stream=True)` downloads the JPEG.

---

## 4  Convert WebP → JPEG in memory (minimal extra loss)

```python
import io, requests
from PIL import Image

buf = io.BytesIO(requests.get(thumb).content)
img = Image.open(buf).convert("RGB")

out = io.BytesIO()
img.save(out, format="JPEG", quality=100, subsampling=0, optimize=True)

with open("face_swap.jpg", "wb") as f:
    f.write(out.getvalue())
```

*JPEG is larger because of the codec; it contains the **same** pixels.
For truly loss‑less storage, keep WebP or save PNG.*

---

## 5  Qt multi‑thread crash – **“QThread destroyed while thread is running”**

**Root cause** – `FaceSwapWorker` inherits `QThread` *and* is moved into
another `QThread`.  Its own base thread is never started/quit, so the C++
destructor complains.

### Correct pattern

```diff
- class FaceSwapWorker(QThread):
+ class FaceSwapWorker(QObject):

  thread = QThread()
  worker.moveToThread(thread)
  thread.started.connect(worker.run)
  worker.finished.connect(thread.quit)
  thread.finished.connect(worker.deleteLater)
```

On shutdown:

```python
for t in self._worker_threads:
    t.quit()
    t.wait()   # returns promptly; terminate() rarely needed
```

This removes the warning and guarantees a clean exit.

---
