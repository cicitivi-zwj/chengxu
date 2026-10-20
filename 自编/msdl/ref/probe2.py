import json, re, ssl, uuid, urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
PROFILE = "606624d44113"

def call(url, extra=None):
    h = {"User-Agent": UA, "Accept": "application/json, text/javascript, */*; q=0.01",
         "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.microsoft.com/en-us/software-download/windows11"}
    if extra: h.update(extra)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
        return r.status, r.read().decode("utf-8", "replace")

sid = str(uuid.uuid4())
url = ("https://www.microsoft.com/software-download-connector/api/getskuinformationbyproductedition"
       f"?profile={PROFILE}&productEditionId=3813&SKU=undefined&friendlyFileName=undefined"
       f"&Locale=en-US&sessionID={sid}")
print("SESSION", sid)
st, body = call(url)
print("status", st, "len", len(body))
print(body[:1500])
try:
    d = json.loads(body)
    print("\n=== parsed keys ===", list(d.keys()))
    skus = d.get("Skus") or []
    print("sku count:", len(skus))
    for s in skus[:8]:
        print("  ", s.get("Id"), "|", s.get("Language"), "|", s.get("LocalizedLanguage"))
except Exception as e:
    print("json fail:", e)
