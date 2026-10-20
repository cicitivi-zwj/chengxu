import json, re, ssl, time, uuid, urllib.request, http.cookiejar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
CJ = http.cookiejar.CookieJar()
OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CJ), urllib.request.HTTPSHandler(context=CTX))
ORG, PROFILE = "y6jn8c31", "606624d44113"
IID = "560dc9f3-1aa5-4a2f-b63c-9e18f8d0e175"
REF = "https://www.microsoft.com/en-us/software-download/windows11"

def call(url, accept="*/*", ref=None):
    h = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
    if ref: h["Referer"] = ref
    with OP.open(urllib.request.Request(url, headers=h), timeout=45) as r:
        return r.status, r.read().decode("utf-8", "replace")

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

def skus(edition_id, sid):
    _, body = call(("https://www.microsoft.com/software-download-connector/api/getskuinformationbyproductedition"
                    f"?profile={PROFILE}&productEditionId={edition_id}&SKU=undefined&friendlyFileName=undefined"
                    f"&Locale=en-US&sessionID={sid}"), "application/json", REF)
    return body

def links(sku, sid):
    _, body = call(("https://www.microsoft.com/software-download-connector/api/GetProductDownloadLinksBySku"
                    f"?profile={PROFILE}&productEditionId=undefined&SKU={sku}&friendlyFileName=undefined"
                    f"&Locale=en-US&sessionID={sid}"), "application/json", REF)
    return body

sid = handshake()
print("handshake ok", sid)
d = skus(3813, sid)
print("RAW:", d[:800])
raise SystemExit(0)
print("cn sku:", cn["Id"] if cn else None, "| build:", cn["ProductDisplayName"] if cn else "")
r = links(cn["Id"], sid)
print("errors:", r.get("Errors"))
for o in r.get("ProductDownloadOptions") or []:
    print(f"  [{o.get('DownloadType')}] {o.get('Uri')}")
