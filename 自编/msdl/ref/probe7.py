import json, re, ssl, time, uuid, urllib.request, http.cookiejar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
CJ = http.cookiejar.CookieJar()
OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CJ),
                                 urllib.request.HTTPSHandler(context=ssl.create_default_context()))
ORG, PROFILE = "y6jn8c31", "606624d44113"
IID = "560dc9f3-1aa5-4a2f-b63c-9e18f8d0e175"
REF = "https://www.microsoft.com/en-us/software-download/windows11"

def call(url, accept="*/*", ref=None):
    h = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
    if ref: h["Referer"] = ref
    with OP.open(urllib.request.Request(url, headers=h), timeout=45) as r:
        return r.status, r.read().decode("utf-8", "replace")

def jload(body):
    d = json.loads(body)
    if isinstance(d, str):
        d = json.loads(d)
    return d

def handshake():
    sid = str(uuid.uuid4())
    call(f"https://vlscppe.microsoft.com/tags?org_id={ORG}&session_id={sid}")
    _, mdt = call(f"https://ov-df.microsoft.com/mdt.js?instanceId={IID}&PageId=si&session_id={sid}")
    w = (re.search(r'[?&]w=([A-F0-9]+)', mdt) or [None, None])[1]
    rt = (re.search(r'rticks="\+?(\d+)', mdt) or [None, None])[1]
    if not (w and rt):
        raise RuntimeError("ov-df 握手失败")
    call(f"https://ov-df.microsoft.com/?session_id={sid}&CustomerId={IID}&PageId=si&w={w}&mdt={int(time.time()*1000)}&rticks={rt}")
    return sid

sid = handshake()
_, body = call(("https://www.microsoft.com/software-download-connector/api/getskuinformationbyproductedition"
                f"?profile={PROFILE}&productEditionId=3813&SKU=undefined&friendlyFileName=undefined"
                f"&Locale=en-US&sessionID={sid}"), "application/json", REF)
d = jload(body)
skus = d.get("Skus") or []
cn = next(s for s in skus if s["Language"] == "Chinese (Simplified)")
print("skus:", len(skus), "| cn:", cn["Id"], cn["ProductDisplayName"])

_, body2 = call(("https://www.microsoft.com/software-download-connector/api/GetProductDownloadLinksBySku"
                 f"?profile={PROFILE}&productEditionId=undefined&SKU={cn['Id']}"
                 f"&friendlyFileName=undefined&Locale=en-US&sessionID={sid}"), "application/json", REF)
r = jload(body2)
print("errors:", r.get("Errors"))
for o in r.get("ProductDownloadOptions") or []:
    print(f"  [{o.get('DownloadType')}]")
    print(f"    {o.get('Uri')}")
