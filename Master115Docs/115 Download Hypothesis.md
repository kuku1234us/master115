i tried typing in "https://115.com/?ct=browser&ac=download_folder&pickcode=fbakskgmti1dquw4am" in the address bar of the 115chrome browser. I got a blank page with no zip file or other downloads initiated.

# Hypothesis:

The key thing to understand is that every file‐ or folder‑row in that iframe is represented by an `<li rel="item">` element which carries, among other things, a `pick_code` attribute. That `pick_code` is the only thing the server needs in order to know which file or folder you want to download.

Inside each `<li>` you’ll see a little `<div class="file-opr" rel="menu">…</div>` containing a bunch of `<a>` tags whose `menu` attributes map to different actions. In particular for downloading a folder it looks like this:

```
<a href="https://115.com/?ct=browser&ac=download_folder&pickcode=fbakskgmti1dquw4am"
   menu="download_dir_one">
  <i class="icon-operate ifo-download"></i><span>下载</span>
</a>
```

**How clicks are wired up**  
In the page’s JavaScript (loaded externally), there is a single delegated click‑handler bound to elements with `[menu]`. Roughly speaking it does:
```
$('body').on('click', '[menu]', function(e){
  var action = $(this).attr('menu');
  Core.FileMenu.DoEvent( /* context */, action );
});
```

and then `Core.FileMenu.DoEvent` looks at `action === 'download_dir_one'`, grabs the `pickcode` from the corresponding `<li>` (or from the `href`), and fires off the download.

**What actually happens on download**  
When you click that `<a>`, your browser navigates to:
```
https://115.com/?ct=browser&ac=download_folder&pickcode=<your‑pickcode>
```
The server then prepares (or streams) a `.zip` of that folder and ultimately sends you back a redirect or a `Content‑Disposition: attachment` response that your browser saves.

**Automating it**  
Since it’s just a normal `<a href="…pickcode=XXX">`, you can automate in two simple ways:

- **Selenium / Playwright**
```
# once you’re logged in and have switched into the iframe:
download_buttons = driver.find_elements_by_css_selector('a[menu="download_dir_one"]')
for btn in download_buttons:
    btn.click()
    # or, to avoid UI timing issues:
    driver.get(btn.get_attribute('href'))
```

- Direct HTTP requests
```
import requests

session = requests.Session()
# copy over your authenticated cookies from the browser into `session`
pickcodes = ['fbakskgmti1dquw4am', …]  # scrape these from the page DOM
for code in pickcodes:
    url = f"https://115.com/?ct=browser&ac=download_folder&pickcode={code}"
    r = session.get(url, allow_redirects=True, stream=True)
    with open(f"{code}.zip", "wb") as f:
        for chunk in r.iter_content(1024*10):
            f.write(chunk)
```

# Typing the address "https://115.com/?ct=browser&ac=download_folder&pickcode=fbakskgmti1dquw4am" directly in the browser address bar

When you paste that `https://115.com/?ct=browser&ac=download_folder&pickcode=fbakskgmti1dquw4am` URL straight into the address bar, what you’re hitting is the _wrapper_ endpoint that the page’s JavaScript normally calls **behind the scenes**—it isn’t itself the ZIP file.

Here’s what happens in the normal UI flow:

1. **You click the “下载” button**
```
<a href="https://115.com/?ct=browser&ac=download_folder&pickcode=fbakskgmti1dquw4am"
   menu="download_dir_one">
  <i class="icon-operate ifo-download"></i><span>下载</span>
</a>
```
That `<a>` tag is only a _placeholder_ for the JavaScript handler.

2. **JavaScript intercepts the click**  
The site binds a delegated click‐handler on `[menu="download_dir_one"]` which does roughly:
```
$('body').on('click', '[menu="download_dir_one"]', function(e){
  e.preventDefault();
  Core.FileMenu.DoEvent(/* … */, 'download_dir_one');
});
```

That `DoEvent('download_dir_one')` call then:

- Sends an AJAX request to the server to _create_ or _fetch_ the .zip package.
    
- Polls a packing‐status API until the ZIP is built.
    
- Finally issues a **redirect** (or dynamically inserts a hidden `<iframe>` or uses `window.location`) to the _real_ download URL, which looks more like:

```
https://down.115.com/xxxxxxx?token=…&expires=…
```
- That final URL streams the actual ZIP with proper `Content‑Disposition: attachment`.

3. **Why typing the wrapper URL by hand shows nothing**
    
    - **No JS execution**: Your browser simply loads that one endpoint and renders whatever minimal HTML/JSON stub it returns (often literally an empty “packing in progress” page or JSON), but never runs the scripts that would kick off the real download.
        
    - **Missing headers / cookies / tokens**: The AJAX flow also passes authentication cookies, CSRF tokens, a user‑ID (`uk`) parameter, etc., which aren’t all present when you just paste the link.

### How to automate properly

- **With Selenium/Playwright**  
    Keep the page loaded, then invoke the same click handler:
```
btn = driver.find_element_by_css_selector('a[menu="download_dir_one"]')
btn.click()
# Or to skip the UI thread:
driver.execute_script("""
  Core.FileMenu.DoEvent(
    /* context */ document.querySelector('a[menu="download_dir_one"]'),
    'download_dir_one'
  );
""")
```

- That ensures you run the packing/polling logic the page provides, and Chrome will automatically download the finished ZIP.
    
- **By reverse‑engineering the API**
    
    1. Inspect the network panel when you click “下载” in a real session.
        
    2. You’ll see calls to something like
```
GET https://webapi.115.com/files/download?pickcode=…&uk=…&cache=…&ssl=1
```

	3. Poll that JSON endpoint until it returns your `"url"`, then do a direct `GET` on that URL with the same cookies:
```
import requests
s = requests.Session()
# populate s.cookies from your logged‑in browser
r = s.get(
    "https://webapi.115.com/files/download",
    params={"pickcode": pickcode, "uk": uk, "ssl": 1},
    headers={"Referer": "https://115.com/"}
)
download_url = r.json()['url']
resp = s.get(download_url, stream=True)
with open(f"{pickcode}.zip","wb") as f:
    for chunk in resp.iter_content(8192):
        f.write(chunk)
```

In short: **that “download_folder” link is not the final file**, it’s just the trigger for the page’s JS packing routine. If you want to automate downloads you must either drive the JS click (so it does its packing/polling) or call the same backend APIs it does and then fetch the final ZIP URL.
