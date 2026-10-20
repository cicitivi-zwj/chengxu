import json, re, ssl, sys, uuid, urllib.request, urllib.error

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()

def get(url, extra=None, timeout=40):
    h = {"User-Agent": UA, "Accept": "text/html,application/json,*/*",
         "Accept-Language": "en-US,en;q=0.9"}
    if extra: h.update(extra)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.status, r.read()

def try_one(label, fn):
    try:
        print(f"--- {label} ---")
        fn()
    except Exception as e:
        print(f"  FAIL {type(e).__name__}: {e}")

def page():
    st, body = get("https://www.microsoft.com/en-us/software-download/windows11")
    txt = body.decode("utf-8", "replace")
    print("  status", st, "len", len(txt))
    opts = re.findall(r'<option[^>]+value="(\d+)"[^>]*>([^<]{2,120})</option>', txt)
    for v, t in opts[:15]:
        print("   ", v, t.strip()[:60])
    print("  option count:", len(opts))

def mdt():
    st, body = get("https://ov-df.microsoft.com/mdt.js?instanceId=560dc9f3-1aa5-4a2f-b63c-9e18f8d0e175")
    t = body.decode("utf-8", "replace")
    print("  status", st, "len", len(t))
    print("  w:", (re.search(r'[?&]w=([A-F0-9]+)', t) or [None, None])[1])
    print("  rticks:", (re.search(r'rticks="\+?(\d+)', t) or [None, None])[1])
    print("  head:", t[:200].replace("\n", " "))

for lbl, fn in [("page windows11", page), ("ov-df mdt.js", mdt)]:
    try_one(lbl, fn)
