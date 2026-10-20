# -*- coding: utf-8 -*-
"""用本地带 Range 支持的 HTTP 服务验证多线程分段/断点续传/合并"""
import hashlib, os, shutil, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re

sys.path.insert(0, r"D:\msdl")
import msdl_core as C

ROOT = r"D:\msdl\_t"
os.makedirs(ROOT, exist_ok=True)
SRC = os.path.join(ROOT, "src.bin")
if not os.path.exists(SRC):
    with open(SRC, "wb") as f:
        for _ in range(20):
            f.write(os.urandom(1024 * 1024))  # 20MB
SIZE = os.path.getsize(SRC)
REAL = hashlib.sha256(open(SRC, "rb").read()).hexdigest()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", str(SIZE))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", 'attachment; filename="Win_Test_x64_zh-cn.iso"')
        self.end_headers()

    def do_GET(self):
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d+)-(\d*)", rng)
            a = int(m.group(1))
            b = int(m.group(2)) if m.group(2) else SIZE - 1
            b = min(b, SIZE - 1)
            self.send_response(206)
            self.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, SIZE))
            self.send_header("Content-Length", str(b - a + 1))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with open(SRC, "rb") as f:
                f.seek(a)
                left = b - a + 1
                while left > 0:
                    chunk = f.read(min(65536, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(SIZE))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with open(SRC, "rb") as f:
                shutil.copyfileobj(f, self.wfile)


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d/src.bin" % port
print("server:", URL, "size", C.human(SIZE))

dest = os.path.join(ROOT, "out.iso")
for p in os.listdir(ROOT):
    if p.startswith("out.iso"):
        os.remove(os.path.join(ROOT, p))

d = C.Downloader(URL, dest, threads=8)
info = d.probe()
print("probe:", info, "| total", C.human(d.total))
print("filename:", info.get("filename"))

t0 = time.time()
d.start()
last = 0
while not d.finished and not d.error and time.time() - t0 < 120:
    n = d.downloaded()
    print("  %5.1f%%  %s" % (100.0 * n / d.total, C.human(n)))
    time.sleep(1.0)

print("finished:", d.finished, "error:", d.error, "耗时 %.1fs" % (time.time() - t0))
if d.finished:
    got = hashlib.sha256(open(dest, "rb").read()).hexdigest()
    print("size match:", os.path.getsize(dest) == SIZE)
    print("sha256 match:", got == REAL)
    print("残留分片:", [p for p in os.listdir(ROOT) if ".part" in p or p.endswith(".msdl.json")])

# 断点续传测试：下到一半停，再续
dest2 = os.path.join(ROOT, "out2.iso")
for p in os.listdir(ROOT):
    if p.startswith("out2.iso"):
        os.remove(os.path.join(ROOT, p))
d2 = C.Downloader(URL, dest2, threads=8)
d2.total = SIZE; d2.resumable = True; d2.probe_info = {"ok": 1}
d2.threads = 8
segs = d2._segments()
d2._save_meta(segs)
for i, (a, b) in enumerate(segs):
    threading.Thread(target=d2._run_segment, args=(i, a, b), daemon=True).start()
time.sleep(0.35)
d2.stop()
time.sleep(0.3)
print("中断时已下:", C.human(d2.downloaded()), "分片:", len([p for p in os.listdir(ROOT) if p.startswith("out2.iso.part")]))

d3 = C.Downloader(URL, dest2, threads=8)
d3.probe()
d3.start()
t1 = time.time()
while not d3.finished and not d3.error and time.time() - t1 < 120:
    time.sleep(0.8)
print("续传完成:", d3.finished, d3.error)
if d3.finished:
    print("续传 sha256 一致:", hashlib.sha256(open(dest2, "rb").read()).hexdigest() == REAL)
srv.shutdown()
