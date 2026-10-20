# -*- coding: utf-8 -*-
"""GUI 暂停/续传测试：限速服务器 + 中途暂停 + 再续传 + 校验哈希"""
import sys, os, time, threading, hashlib, shutil, re
sys.path.insert(0, r"D:\msdl")
import tkinter as tk
import msdl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = r"D:\msdl\_t"
SRC = os.path.join(ROOT, "src.bin")
SIZE = os.path.getsize(SRC)
REAL = hashlib.sha256(open(SRC, "rb").read()).hexdigest()
THROTTLE = 0.012   # 每 64KB 停顿，模拟 ~5MB/s


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", str(SIZE))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", 'attachment; filename="Resume_Test.iso"')
        self.end_headers()

    def do_GET(self):
        m = re.match(r"bytes=(\d+)-(\d*)", self.headers.get("Range") or "")
        if m:
            a = int(m.group(1)); b = int(m.group(2) or SIZE - 1); b = min(b, SIZE - 1)
            self.send_response(206)
            self.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, SIZE))
            self.send_header("Content-Length", str(b - a + 1))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with open(SRC, "rb") as f:
                f.seek(a); left = b - a + 1
                while left > 0:
                    c = f.read(min(65536, left))
                    if not c:
                        break
                    self.wfile.write(c)
                    left -= len(c)
                    time.sleep(THROTTLE)
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(SIZE))
            self.end_headers()
            with open(SRC, "rb") as f:
                shutil.copyfileobj(f, self.wfile)


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

root = tk.Tk()
app = msdl.App(root)
# 直接给 URL 跳过微软接口（本次只测下载引擎）
app.url = "http://127.0.0.1:%d/src.bin" % srv.server_address[1]
outdir = os.path.join(ROOT, "resume")
os.makedirs(outdir, exist_ok=True)
for p in os.listdir(outdir):
    os.remove(os.path.join(outdir, p))
app.var_dir.set(outdir)
app.var_threads.set(8)
# 覆盖确认对话框：测试环境预先放一个假目标文件让 askyesno 触发不了——绕开：直接保证目标不存在
app._on_download()

# 等到 30% 暂停
t0 = time.time()
paused = False
while time.time() - t0 < 60:
    root.update()
    time.sleep(0.02)
    if not paused and app.dl and app.dl.total and app.dl.downloaded() > app.dl.total * 0.30:
        app._on_pause()
        paused = True
        print("已触发暂停 @", app.dl.downloaded())
    if app.dl_state == "paused":
        break
print("状态:", app.dl_state, "|", app.lbl_prog.cget("text"))
parts = [p for p in os.listdir(outdir) if p.startswith("Resume_Test.iso.part")]
print("保留分片:", len(parts), sorted(parts)[:3])
mid = app.dl.downloaded() if app.dl else 0
print("已下:", mid, "bytes")

# 续传
app._on_download()
t0 = time.time()
while time.time() - t0 < 120 and app.dl_state in ("running", "paused"):
    root.update()
    time.sleep(0.02)
    if app.dl_state == "done":
        break
print("最终状态:", app.dl_state, "|", app.lbl_prog.cget("text"))
iso = os.path.join(outdir, "Resume_Test.iso")
if os.path.exists(iso):
    print("大小一致:", os.path.getsize(iso) == SIZE)
    print("哈希一致:", hashlib.sha256(open(iso, "rb").read()).hexdigest() == REAL)
print("残留分片:", [p for p in os.listdir(outdir) if ".part" in p or p.endswith(".msdl.json")])
srv.shutdown()
root.destroy()
