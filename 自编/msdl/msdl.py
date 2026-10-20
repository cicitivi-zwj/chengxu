# -*- coding: utf-8 -*-
"""
MSDL —— 微软官方镜像下载器
仅调用 www.microsoft.com/software-download 官方接口，多线程分段下载，支持断点续传。

与本机那个 wrxz.exe 的区别：
  无 ver.ini 配置下发、无自动更新通道、无远程控制工具下载、
  无 #RequireAdmin 提权、不写注册表、不建计划任务、不采集主机信息。
"""
import os
import queue
import shutil
import sys
import threading
import time
import tkinter as tk
import urllib.parse
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import msdl_core as core

APP_TITLE = "MSDL · 微软官方镜像下载器"
FONT = ("Microsoft YaHei UI", 10)
FONT_S = ("Microsoft YaHei UI", 9)
FONT_B = ("Microsoft YaHei UI", 11, "bold")
FONT_T = ("Microsoft YaHei UI", 16, "bold")

LANG_CN = "Chinese (Simplified)"


class App(object):
    def __init__(self, root):
        self.root = root
        self.api = core.MicrosoftISO(locale="zh-CN")
        self.q = queue.Queue()
        self.editions = {}          # label -> id
        self.languages = []         # list of dict
        self.url = ""
        self.dl = None
        self.dl_state = "idle"      # idle | running | paused | done
        self._last_bytes = 0
        self._last_time = 0.0
        self._speed = 0.0
        self._sha_stop = threading.Event()
        self._busy = False
        self._tasks = queue.Queue()
        threading.Thread(target=self._task_loop, daemon=True).start()

        self._build_ui()
        self.root.after(120, self._pump)
        self._load_editions()

    def _task_loop(self):
        """单线程顺序执行后台任务：避免并发握手触发微软风控。"""
        while True:
            fn, a = self._tasks.get()
            try:
                fn(*a)
            except Exception as e:
                self.q.put(("error", str(e)))

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.root.title(APP_TITLE)
        self.root.geometry("880x660")
        self.root.minsize(820, 620)

        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure(".", font=FONT)
        style.configure("TLabel", font=FONT)
        style.configure("TCheckbutton", font=FONT)
        style.configure("TButton", font=FONT)
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TLabelframe.Label", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Big.TButton", font=("Microsoft YaHei UI", 10, "bold"), padding=(16, 8))
        style.configure("Hint.TLabel", font=FONT_S, foreground="#666666")

        # 顶部标题
        head = tk.Frame(self.root, bg="#1f6feb", height=78)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text="MSDL", bg="#1f6feb", fg="white", font=FONT_T).pack(side="left", padx=(20, 10), pady=14)
        box = tk.Frame(head, bg="#1f6feb")
        box.pack(side="left", pady=14)
        tk.Label(box, text="微软官方镜像下载器", bg="#1f6feb", fg="white",
                 font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        tk.Label(box, text="官方接口直链 · 多线程分段 · 断点续传 · 不联网上报",
                 bg="#1f6feb", fg="#cfe2ff", font=("Microsoft YaHei UI", 9)).pack(anchor="w")

        main = ttk.Frame(self.root, padding=(16, 12, 16, 8))
        main.pack(fill="both", expand=True)

        # ---- 1 选择版本
        g1 = ttk.LabelFrame(main, text=" 1  选择镜像 ", padding=(12, 8))
        g1.pack(fill="x")

        row = ttk.Frame(g1)
        row.pack(fill="x")
        ttk.Label(row, text="产品", width=6).pack(side="left")
        self.cb_product = ttk.Combobox(row, state="readonly", width=16,
                                       values=[p[0] for p in core.PRODUCTS])
        self.cb_product.current(0)
        self.cb_product.pack(side="left", padx=(0, 16))
        self.cb_product.bind("<<ComboboxSelected>>", lambda e: self._load_editions())

        ttk.Label(row, text="版本", width=6).pack(side="left")
        self.cb_edition = ttk.Combobox(row, state="readonly", width=34)
        self.cb_edition.pack(side="left", padx=(0, 16))
        self.cb_edition.bind("<<ComboboxSelected>>", lambda e: self._load_languages())

        ttk.Label(row, text="语言", width=6).pack(side="left")
        self.cb_lang = ttk.Combobox(row, state="readonly", width=24)
        self.cb_lang.pack(side="left")

        row2 = ttk.Frame(g1)
        row2.pack(fill="x", pady=(10, 0))
        self.btn_query = ttk.Button(row2, text="获取官方下载链接", style="Big.TButton",
                                    command=self._on_query)
        self.btn_query.pack(side="left")
        self.lbl_query = ttk.Label(row2, text="", style="Hint.TLabel")
        self.lbl_query.pack(side="left", padx=12)

        # ---- 2 链接
        g2 = ttk.LabelFrame(main, text=" 2  下载直链 ", padding=(12, 8))
        g2.pack(fill="x", pady=(10, 0))
        self.txt_url = tk.Text(g2, height=3, wrap="char", font=("Consolas", 9),
                               relief="solid", bd=1, bg="#f7f8fa")
        self.txt_url.pack(fill="x")
        self.txt_url.configure(state="disabled")
        r2 = ttk.Frame(g2)
        r2.pack(fill="x", pady=(8, 0))
        self.btn_copy = ttk.Button(r2, text="复制直链", command=self._on_copy, state="disabled")
        self.btn_copy.pack(side="left")
        self.lbl_meta = ttk.Label(r2, text="", style="Hint.TLabel")
        self.lbl_meta.pack(side="left", padx=12)

        # ---- 3 下载
        g3 = ttk.LabelFrame(main, text=" 3  保存并下载 ", padding=(12, 8))
        g3.pack(fill="x", pady=(10, 0))
        r3 = ttk.Frame(g3)
        r3.pack(fill="x")
        ttk.Label(r3, text="保存到", width=6).pack(side="left")
        self.var_dir = tk.StringVar(value=self._default_dir())
        ttk.Entry(r3, textvariable=self.var_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(r3, text="浏览…", width=8, command=self._pick_dir).pack(side="left", padx=(8, 0))

        r4 = ttk.Frame(g3)
        r4.pack(fill="x", pady=(10, 0))
        ttk.Label(r4, text="线程", width=6).pack(side="left")
        self.var_threads = tk.IntVar(value=8)
        ttk.Spinbox(r4, from_=1, to=16, width=5, textvariable=self.var_threads).pack(side="left")
        ttk.Label(r4, text="（1 = 单线程；多线程需服务器支持 Range）",
                  style="Hint.TLabel").pack(side="left", padx=(8, 0))

        self.btn_dl = ttk.Button(r4, text="开始下载", style="Big.TButton",
                                 command=self._on_download, state="disabled")
        self.btn_dl.pack(side="right")
        self.btn_pause = ttk.Button(r4, text="暂停", command=self._on_pause, state="disabled")
        self.btn_pause.pack(side="right", padx=(0, 8))

        self.pb = ttk.Progressbar(g3, mode="determinate", maximum=100)
        self.pb.pack(fill="x", pady=(12, 4))
        self.lbl_prog = ttk.Label(g3, text="等待获取链接", style="Hint.TLabel")
        self.lbl_prog.pack(anchor="w")

        # ---- 日志
        g4 = ttk.LabelFrame(main, text=" 运行信息 ", padding=(8, 6))
        g4.pack(fill="both", expand=True, pady=(10, 0))
        self.log = tk.Text(g4, height=8, wrap="word", font=("Consolas", 9),
                           relief="flat", bg="#fbfbfc", state="disabled")
        self.log.pack(fill="both", expand=True, side="left")
        sb = ttk.Scrollbar(g4, command=self.log.yview)
        sb.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=sb.set)

        # 底部
        foot = ttk.Frame(self.root, padding=(16, 4, 16, 10))
        foot.pack(fill="x")
        ttk.Label(foot, text="数据来源：www.microsoft.com 官方接口。链接有效期约 24 小时，过期请重新获取。",
                  style="Hint.TLabel").pack(side="left")
        ttk.Button(foot, text="关于", width=6, command=self._about).pack(side="right")

        self._log("就绪。选择产品与版本后点「获取官方下载链接」。")
        self._log("本工具不读取任何配置文件、不检查更新、不下载微软官方 ISO 以外的任何可执行文件。")

    def _default_dir(self):
        d = os.path.join(os.path.expanduser("~"), "Downloads")
        return d if os.path.isdir(d) else os.path.expanduser("~")

    # ------------------------------------------------------------ 后台任务
    def _bg(self, fn, *a):
        self._tasks.put((fn, a))

    def _pump(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "editions":
                    self._apply_editions(payload)
                elif kind == "languages":
                    self._apply_languages(payload)
                elif kind == "link":
                    self._apply_link(payload)
                elif kind == "error":
                    self._on_error(payload)
                elif kind == "dl":
                    self._on_dl_tick(payload)
                elif kind == "sha":
                    self._log("SHA256: " + payload)
                    self.lbl_prog.configure(text="下载完成 · SHA256 已计算\n" + payload)
                elif kind == "busy":
                    self._set_busy(payload)
        except queue.Empty:
            pass
        self._tick_progress()
        self.root.after(120, self._pump)

    def _set_busy(self, flag):
        self.btn_query.configure(state="disabled" if flag else "normal")

    def _log(self, s):
        self.log.configure(state="normal")
        self.log.insert("end", time.strftime("[%H:%M:%S] ") + s + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _on_error(self, msg):
        self._log("失败：" + msg)
        self.lbl_query.configure(text="失败")
        messagebox.showerror("出错了", msg)

    # ------------------------------------------------------------ 版本/语言
    def _product_slug(self):
        i = self.cb_product.current()
        return core.PRODUCTS[i][1]

    def _load_editions(self):
        self.cb_edition.set("")
        self.cb_lang.set("")
        self.editions = {}
        self.languages = []
        self.btn_dl.configure(state="disabled")
        self.lbl_query.configure(text="正在读取版本列表…")
        slug = self._product_slug()
        self.q.put(("busy", True))
        self._bg(self._task_editions, slug)

    def _task_editions(self, slug):
        try:
            eds = self.api.editions(slug)
            self.q.put(("editions", eds))
        finally:
            self.q.put(("busy", False))

    def _apply_editions(self, eds):
        self.editions = {label: eid for eid, label in eds}
        labels = [label for _, label in eds]
        self.cb_edition.configure(values=labels)
        if labels:
            self.cb_edition.current(0)
            self._log("可用版本 %d 个：%s" % (len(labels), "；".join(labels)))
            self._load_languages()
        else:
            self.lbl_query.configure(text="未取到版本列表")
            self._log("未取到版本列表，可能是微软页面结构变化或网络受限。")

    def _load_languages(self):
        label = self.cb_edition.get()
        if not label or label not in self.editions:
            return
        self.cb_lang.set("")
        self.languages = []
        self.lbl_query.configure(text="正在读取语言列表…")
        self.q.put(("busy", True))
        self._bg(self._task_languages, self.editions[label], self._product_slug())

    def _task_languages(self, eid, slug):
        try:
            rows = self.api.languages(eid, slug)
            self.q.put(("languages", rows))
        finally:
            self.q.put(("busy", False))

    def _apply_languages(self, rows):
        self.languages = rows
        names = []
        for r in rows:
            n = r["localized"] or r["language"]
            if r["language"] == LANG_CN:
                n = "简体中文"
            elif r["language"] == "Chinese (Traditional)":
                n = "繁体中文"
            names.append(n)
        self._lang_names = names
        self.cb_lang.configure(values=names)
        idx = rows and next((i for i, r in enumerate(rows) if r["language"] == LANG_CN), 0)
        self.cb_lang.current(idx if names else -1)
        build = rows[0]["build"] if rows else ""
        self.lbl_query.configure(text="已就绪 · %s" % build)
        self._log("语言 %d 种，构建版本：%s" % (len(rows), build))

    # ------------------------------------------------------------ 取链接
    def _on_query(self):
        i = self.cb_lang.current()
        if i < 0 or i >= len(self.languages):
            messagebox.showinfo("提示", "请先选择语言。")
            return
        row = self.languages[i]
        slug = self._product_slug()          # 控件只能在主线程读
        self.lbl_query.configure(text="正在向微软请求直链…")
        self.q.put(("busy", True))
        self.btn_query.configure(state="disabled")
        self._bg(self._task_link, row["sku"], row["localized"] or row["language"], slug)

    def _task_link(self, sku, lang_name, slug):
        try:
            links = self.api.links(sku, slug, session_id=self.api._last_session)
            self.q.put(("link", {"url": links[0][1], "sku": sku, "lang": lang_name}))
        finally:
            self.q.put(("busy", False))

    def _apply_link(self, info):
        self.url = info["url"]
        name = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(self.url).path))
        self.txt_url.configure(state="normal")
        self.txt_url.delete("1.0", "end")
        self.txt_url.insert("1.0", self.url)
        self.txt_url.configure(state="disabled")
        self.btn_copy.configure(state="normal")
        self.lbl_meta.configure(text="%s ｜ %s" % (name, info["lang"]))
        self.lbl_query.configure(text="直链已获取")
        self.btn_dl.configure(state="normal")
        self._log("已获取直链（文件名 %s），有效期约 24 小时。" % name)
        self.pb["value"] = 0
        self.lbl_prog.configure(text="待下载")

    def _on_copy(self):
        if not self.url:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.url)
        self._log("直链已复制到剪贴板（可交给 IDM / aria2 等工具使用）。")

    # ------------------------------------------------------------ 下载
    def _pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.var_dir.get() or self._default_dir())
        if d:
            self.var_dir.set(d)

    def _on_download(self):
        if self.dl_state == "running":
            return
        if not self.url:
            return
        d = self.var_dir.get().strip()
        if not d or not os.path.isdir(d):
            messagebox.showinfo("提示", "请选择一个有效的保存目录。")
            return
        raw = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(self.url).path))
        fallback = not raw.lower().endswith((".iso", ".img"))
        name = "Windows_Image.iso" if fallback else raw
        dest = os.path.join(d, name)
        self._dest = dest
        if os.path.exists(dest):
            if not messagebox.askyesno("文件已存在", "%s 已存在，是否覆盖？" % name):
                return
            try:
                os.remove(dest)
            except OSError as e:
                messagebox.showerror("无法覆盖", str(e))
                return
            for i in range(17):          # 覆盖时把旧分片一并清掉
                for suf in (".part%d" % i, ".msdl.json"):
                    p = dest + suf
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass
        self.dl_state = "running"
        self.btn_dl.configure(state="disabled")
        self.btn_pause.configure(state="normal", text="暂停")
        self._last_bytes, self._last_time, self._speed = 0, time.time(), 0.0
        self._log("开始下载 → %s（%d 线程）" % (dest, self.var_threads.get()))
        threading.Thread(target=self._task_download, args=(dest, self.var_threads.get(), fallback),
                         daemon=True).start()

    def _task_download(self, dest, threads, allow_rename=False):
        try:
            self.dl = core.Downloader(self.url, dest, threads=threads)
            info = self.dl.probe()
            # 若 URL 里没有像样的文件名，改用微软返回的 Content-Disposition
            cd_name = info.get("filename") or ""
            if allow_rename and cd_name.lower().endswith((".iso", ".img")):
                cand = os.path.join(os.path.dirname(dest), cd_name)
                if not os.path.exists(cand):
                    self.dl.set_dest(cand)
                    dest = cand
                    self.q.put(("log", "文件名取自微软响应：%s" % cd_name))
            total = self.dl.total
            self.q.put(("log", "文件大小 %s，%s分段下载。" %
                        (core.human(total), "支持" if self.dl.resumable else "不支持")))
            free = shutil.disk_usage(os.path.dirname(dest)).free
            if total and free < total + 512 * 1024 * 1024:
                self.q.put(("error", "磁盘剩余空间不足：需要约 %s，当前可用 %s"
                            % (core.human(total), core.human(free))))
                self.q.put(("dl", {"state": "error"}))
                return
            self.dl.start()
            while True:
                time.sleep(0.5)
                if self.dl.finished or self.dl.error:
                    break
                if self.dl_state != "running":
                    break
            if self.dl.error:
                self.q.put(("error", self.dl.error))
                self.q.put(("dl", {"state": "error"}))
            elif self.dl.finished:
                self.q.put(("log", "下载完成，正在校验完整性…"))
                h = core.sha256_file(dest)
                self.q.put(("sha", h))
                self.q.put(("dl", {"state": "done"}))
            else:
                self.q.put(("log", "已暂停。分片文件已保留，再次开始将从断点继续。"))
                self.q.put(("dl", {"state": "paused"}))
        except Exception as e:
            self.q.put(("error", str(e)))
            self.q.put(("dl", {"state": "error"}))

    def _on_pause(self):
        if self.dl_state != "running" or self.dl is None:
            return
        self.dl_state = "paused"
        self.dl.stop()
        self.btn_pause.configure(state="disabled", text="暂停中…")

    def _on_dl_tick(self, payload):
        st = payload.get("state")
        if st == "done":
            self.dl_state = "done"
            self.pb["value"] = 100
            self.lbl_prog.configure(text="下载完成 · %s" % core.human(self.dl.total if self.dl else 0))
            self.btn_dl.configure(state="normal", text="重新下载")
            self.btn_pause.configure(state="disabled")
        elif st == "paused":
            self.dl_state = "paused"
            self.btn_dl.configure(state="normal", text="继续下载")
            self.btn_pause.configure(state="disabled", text="已暂停")
            self.lbl_prog.configure(text="已暂停 · 已下 %s" % core.human(self.dl.downloaded() if self.dl else 0))
        elif st == "error":
            self.dl_state = "idle"
            self.btn_dl.configure(state="normal", text="重试")
            self.btn_pause.configure(state="disabled")

    def _tick_progress(self):
        if self.dl_state != "running" or not self.dl:
            return
        n = self.dl.downloaded()
        total = self.dl.total or 0
        now = time.time()
        if self._last_time and now > self._last_time:
            inst = (n - self._last_bytes) / (now - self._last_time)
            self._speed = inst if self._speed == 0 else (self._speed * 0.6 + inst * 0.4)
        self._last_bytes, self._last_time = n, now
        if total:
            pct = min(100.0, 100.0 * n / total)
            self.pb["value"] = pct
            eta = ""
            if self._speed > 1024:
                left = (total - n) / self._speed
                eta = " · 剩余 %s" % self._fmt_eta(left)
            self.lbl_prog.configure(
                text="%.1f%%  %s / %s  ·  %s/s%s"
                     % (pct, core.human(n), core.human(total), core.human(self._speed), eta))
        else:
            self.lbl_prog.configure(text="已下 %s · %s/s" % (core.human(n), core.human(self._speed)))

    @staticmethod
    def _fmt_eta(sec):
        sec = int(sec)
        if sec < 60:
            return "%d 秒" % sec
        if sec < 3600:
            return "%d 分 %d 秒" % (sec // 60, sec % 60)
        return "%d 时 %d 分" % (sec // 3600, (sec % 3600) // 60)

    # ------------------------------------------------------------ 关于
    def _about(self):
        messagebox.showinfo("关于 MSDL", (
            "MSDL · 微软官方镜像下载器\n\n"
            "功能：从微软官方接口获取 Windows ISO 直链并多线程下载。\n"
            "  · 版本与语言列表实时读取自 microsoft.com 下载页\n"
            "  · 直链由微软官方接口签发，有效期约 24 小时\n"
            "  · 支持 1–16 线程分段下载与断点续传\n"
            "  · 下载完成后在本机计算 SHA256（微软未公开此 ISO 的官方哈希，仅作记录/比对用）\n\n"
            "明确不做的：\n"
            "  · 不读取任何配置文件（无 ver.ini 之类的下发通道）\n"
            "  · 不检查更新、不自我替换\n"
            "  · 不下载/运行任何第三方工具（浏览器、远控、解压器等）\n"
            "  · 不需要管理员权限，不写注册表，不建计划任务，不上报任何主机信息\n\n"
            "仅使用 Python 标准库，无第三方依赖。"))


def selftest():
    """--selftest：不开窗口，验证接口与下载引擎（用于打包后自检）"""
    lines = []

    def out(s):
        lines.append(s)
        try:
            print(s)
        except Exception:
            pass

    out("MSDL 自检")
    out("  Python: %s" % sys.version.split()[0])
    api = core.MicrosoftISO(locale="zh-CN")
    ok = 0
    targets = core.PRODUCTS if "--all" in sys.argv else core.PRODUCTS[:1]
    for name, slug in targets:
        try:
            eds = api.editions(slug)
            out("  %s 版本数: %d -> %s" % (name, len(eds), [e[1] for e in eds]))
            if not eds:
                continue
            rows = api.languages(eds[0][0], slug)
            cn = next((r for r in rows if r["language"] == LANG_CN), rows[0])
            out("     语言数: %d | 中文 SKU: %s | 构建: %s" % (len(rows), cn["sku"], cn["build"]))
            links = api.links(cn["sku"], slug, session_id=api._last_session)
            d = core.Downloader(links[0][1], os.path.join(os.path.expanduser("~"), "_msdl_probe.iso"))
            info = d.probe()
            out("     直链: %s..." % links[0][1][:70])
            out("     大小: %s | 分段支持: %s | 文件名: %s"
                % (core.human(d.total), d.resumable, info.get("filename")))
            ok += 1
        except Exception as e:
            out("     失败: %s" % e)
    out("  自检完成，%d 项通过" % ok)

    try:
        import tempfile
        p = os.path.join(tempfile.gettempdir(), "msdl_selftest.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
