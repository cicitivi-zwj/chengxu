import json, ssl, uuid, urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
PROFILE = "606624d44113"

def call(url):
    h = {"User-Agent": UA, "Accept": "application/json, text/javascript, */*; q=0.01",
         "Accept-Language": "en-US,en;q=0.9",
         "Referer": "https://www.microsoft.com/en-us/software-download/windows11"}
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        return r.status, r.read().decode("utf-8", "replace")

sid = str(uuid.uuid4())
url = ("https://www.microsoft.com/software-download-connector/api/GetProductDownloadLinksBySku"
       f"?profile={PROFILE}&productEditionId=undefined&SKU=27157"
       f"&friendlyFileName=undefined&Locale=en-US&sessionID={sid}")
st, body = call(url)
print("status", st, "len", len(body))
d = json.loads(body)
print("keys:", list(d.keys()))
print("errors:", d.get("Errors"))
for opt in d.get("ProductDownloadOptions") or []:
    print("--")
    for k, v in opt.items():
        print(f"   {k} = {str(v)[:150]}")
