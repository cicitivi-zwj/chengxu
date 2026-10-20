import json, re, ssl, time, uuid, urllib.request, http.cookiejar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
CJ = http.cookiejar.CookieJar()
OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CJ), urllib.request.HTTPSHandler(context=CTX))

ORG, PROFILE = "y6jn8c31", "606624d44113"
IID = "560dc9f3-1aa5-4a2f-b63c-9e18f8d0e175"

def call(url, accept="*/*", ref=None):
    h = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
    if ref: h["Referer"] = ref
    req = urllib.request.Request(url, headers=h)
    with OP.open(req, timeout=45) as r:
        return r.status, r.read().decode("utf-8", "replace")

sid = str(uuid.uuid4())
print("session:", sid)

st, _ = call(f"https://vlscppe.microsoft.com/tags?org_id={ORG}&session_id={sid}")
print("1) vlscppe:", st)

st, mdt = call(f"https://ov-df.microsoft.com/mdt.js?instanceId={IID}&PageId=si&session_id={sid}")
print("2) mdt.js:", st, "len", len(mdt))
print("   ", mdt[:300].replace("\n", " "))
w = (re.search(r'[?&]w=([A-F0-9]+)', mdt) or [None, None])[1]
rt = (re.search(r'rticks="\+?(\d+)', mdt) or [None, None])[1]
print("   w =", w, " rticks =", rt)

if w and rt:
    mdtms = int(time.time() * 1000)
    st, _ = call(f"https://ov-df.microsoft.com/?session_id={sid}&CustomerId={IID}&PageId=si&w={w}&mdt={mdtms}&rticks={rt}")
    print("3) ov-df reply:", st)

url = ("https://www.microsoft.com/software-download-connector/api/getskuinformationbyproductedition"
       f"?profile={PROFILE}&productEditionId=3813&SKU=undefined&friendlyFileName=undefined"
       f"&Locale=en-US&sessionID={sid}")
st, body = call(url, "application/json", "https://www.microsoft.com/en-us/software-download/windows11")
print("4) skuinfo:", st, "len", len(body))
d = json.loads(body)
print("   errors:", d.get("ValidationContainer", {}).get("Errors"))
skus = d.get("Skus") or []
print("   skus:", len(skus))
cn = [s for s in skus if s["Language"] == "Chinese (Simplified)"]
print("   cn sku:", cn[0]["Id"] if cn else None)

if cn:
    sid2 = sid
    st, body2 = call(("https://www.microsoft.com/software-download-connector/api/GetProductDownloadLinksBySku"
                      f"?profile={PROFILE}&productEditionId=undefined&SKU={cn[0]['Id']}"
                      f"&friendlyFileName=undefined&Locale=en-US&sessionID={sid2}"),
                     "application/json", "https://www.microsoft.com/en-us/software-download/windows11")
    d2 = json.loads(body2)
    print("5) links:", st, "errors:", d2.get("Errors"))
    for opt in d2.get("ProductDownloadOptions") or []:
        print("   ", opt.get("DownloadType"), "->", str(opt.get("Uri"))[:120])
