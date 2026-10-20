# -*- coding: utf-8 -*-
"""验证 GUI 的 取链接 + 下载 + SHA256 全链路"""
import sys, os, time, threading, hashlib, shutil, re
sys.path.insert(0, r"D:\msdl")
import tkinter as tk
import msdl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = r"D:\msdl\_t"
SRC = os.path.join(ROOT, "src.bin")
SIZE = os.path.getsize(SRC)
REAL = hashlib.sha256(open(SRC, "rb").read()).hexdigest()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _hdr(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", 'attachment; filename="Test_Image_x64_zh-cn.iso"')

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", str(SIZE))
        self._hdr()
        self.end_headers()

    def do_GET(self):
        m = re.match(r"bytes=(\d+)-(\d*)", self.headers.get("Range") or "")
        if m:
            a = int(m.group(1)); b = int(m.group(2) or SIZE - 1); b = min(b, SIZE - 1)
            self.send_response(206)
            self.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, SIZE))
            self.send_header("Content-Length", str(b - a + 1))
            self._hdr()
            self.end_headers()
            with open(SRC, "rb") as f:
                f.seek(a); left = b - a + 1
                while left > 0:
                    c = f.read(min(65536, left))
                    if not c: break
                    self.wfile.write(c); left -= len(c)
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(SIZE))
            self._hdr()
            self.end_headers()
            with open(SRC, "rb") as f:
                shutil.copyfileobj(f, self.wfile)


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d/src.bin" % srv.server_address[1]

root = tk.Tk()
app = msdl.App(root)
# 等版本+语言加载完
t0 = time.time()
while time.time() - t0 < 16 and not app.languages:
    root.update(); time.sleep(0.03)
print("语言就绪:", len(app.languages))

# --- 1) 真实取链接（走微软官方接口）
app._on_query()
t0 = time.time()
while time.time() - t0 < 45 and not app.url:
    root.update(); time.sleep(0.03)
print("真实直链:", (app.url[:90] + "...") if app.url else "未取到")
print("元信息:", app.lbl_meta.cget("text"))
print("下载按钮:", app.btn_dl.cget("state"))

# --- 2) 换成小文件，验证下载链路
outdir = os.path.join(ROOT, "out")
os.makedirs(outdir, exist_ok=True)
for p in os.listdir(outdir):
    os.remove(os.path.join(outdir, p))
app.url = URL
app.var_dir.set(outdir)
app.var_threads.set(6)
app._on_download()
t0 = time.time()
while time.time() - t0 < 90 and app.dl_state == "running":
    root.update(); time.sleep(0.03)
for _ in range(30):
    root.update(); time.sleep(0.05)

print("下载状态:", app.dl_state, "|", app.lbl_prog.cget("text"))
files = os.listdir(outdir)
print("产物:", files)
iso = os.path.join(outdir, "Test_Image_x64_zh-cn.iso")
if os.path.exists(iso):
    print("大小一致:", os.path.getsize(iso) == SIZE)
    print("哈希一致:", hashlib.sha256(open(iso, "rb").read()).hexdigest() == REAL)
print("--- 日志尾部 ---")
print("\n".join(app.log.get("1.0", "end").strip().splitlines()[-8:]))
srv.shutdown()
root.destroy()
