import json, re, ssl, time, uuid, urllib.request, http.cookiejar
import probe7 as P  # reuse helpers

def head(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as r:
            return r.status, dict(r.headers)
    except Exception as e:
        return None, str(e)

def range_get(url, a, b):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Range": f"bytes={a}-{b}"})
    with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as r:
        return r.status, len(r.read()), r.headers.get("Content-Range")

if __name__ == "__main__":
    url = P.get_link()
    print("url ok, len", len(url))
    st, h = head(url)
    print("HEAD:", st)
    if isinstance(h, dict):
        for k in ("Content-Length", "Accept-Ranges", "Content-Type", "Content-Disposition", "Last-Modified"):
            print(f"  {k}: {h.get(k)}")
    print("RANGE 0-1048575:", range_get(url, 0, 1048575))
    print("RANGE 1048576-2097151:", range_get(url, 1048576, 2097151))

    # ARM64 版本是否存在
    sid = P.handshake()
    for eid in (3816, 3814, 3815):
        try:
            d = P.skuinfo(eid, sid)
            sk = d.get("Skus") or []
            print(f"edition {eid}: {len(sk)} langs, {sk[0]['ProductDisplayName'] if sk else '-'}")
        except Exception as e:
            print(f"edition {eid}: FAIL {e}")
