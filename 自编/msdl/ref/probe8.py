import json, re, ssl, time, uuid, urllib.request, http.cookiejar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
CJ = http.cookiejar.CookieJar()
OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CJ),
                                 urllib.request.HTTPSHandler(context=ssl.create_default_context()))
ORG, PROFILE = "y6jn8c31", "606624d44113"
IID = "560dc9f3-1aa5-4a2f-b63c-9e18f8d0e175"

def call(url, accept="*/*", ref=None, timeout=45):
    h = {"User-Agent": UA, "Accept": accept, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
    if ref: h["Referer"] = ref
    with OP.open(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")

def jload(b):
    d = json.loads(b)
    return json.loads(d) if isinstance(d, str) else d

def handshake():
    sid = str(uuid.uuid4())
    call(f"https://vlscppe.microsoft.com/tags?org_id={ORG}&session_id={sid}")
    _, mdt = call(f"https://ov-df.microsoft.com/mdt.js?instanceId={IID}&PageId=si&session_id={sid}")
    w = (re.search(r'[?&]w=([A-F0-9]+)', mdt) or [None, None])[1]
    rt = (re.search(r'rticks="\+?(\d+)', mdt) or [None, None])[1]
    call(f"https://ov-df.microsoft.com/?session_id={sid}&CustomerId={IID}&PageId=si&w={w}&mdt={int(time.time()*1000)}&rticks={rt}")
    return sid

print("=== Win11 页面（zh-cn）所有 option ===")
for loc in ("zh-cn", "en-us"):
    st, html = call(f"https://www.microsoft.com/{loc}/software-download/windows11")
    opts = re.findall(r'<option[^>]+value="(\d+)"[^>]*>([^<]{2,150})</option>', html)
    print(f"  [{loc}] {st} options={len(opts)}")
    for v, t in opts:
        print("    ", v, t.strip()[:70])

print("=== Win10 页面（zh-cn）所有 option ===")
st, html10 = call("https://www.microsoft.com/zh-cn/software-download/windows10ISO")
opts10 = re.findall(r'<option[^>]+value="(\d+)"[^>]*>([^<]{2,150})</option>', html10)
print(" ", st, "options=", len(opts10))
for v, t in opts10:
    print("    ", v, t.strip()[:70])

print("=== Win10 skuinfo 测试 ===")
sid = handshake()
for eid in (2618, 2378):
    try:
        _, b = call(("https://www.microsoft.com/software-download-connector/api/getskuinformationbyproductedition"
                     f"?profile={PROFILE}&productEditionId={eid}&SKU=undefined&friendlyFileName=undefined"
                     f"&Locale=zh-CN&sessionID={sid}"), "application/json",
                    "https://www.microsoft.com/zh-cn/software-download/windows10ISO")
        d = jload(b)
        skus = d.get("Skus") or []
        names = [s["Language"] for s in skus]
        print(f"  edition {eid}: {len(skus)} langs; cn={[s['Id'] for s in skus if s['Language']=='Chinese (Simplified)']} build={skus[0]['ProductDisplayName'] if skus else '?'}")
    except Exception as e:
        print(f"  edition {eid}: FAIL {e}")
