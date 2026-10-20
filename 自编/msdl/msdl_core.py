# -*- coding: utf-8 -*-
"""
msdl_core.py —— 微软官方 ISO 下载核心（纯标准库）

设计原则（与原 wrxz.exe 的差别）：
  * 只使用微软官方公开接口 www.microsoft.com/software-download-connector
  * 不含任何配置下发 / 自动更新 / 远程工具下载 / 提权逻辑
  * 不需要管理员权限，不写注册表，不创建计划任务
"""
import hashlib
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

API = "https://www.microsoft.com/software-download-connector/api"
PROFILE_ID = "606624d44113"     # 微软下载页前端固定使用的 profile
ORG_ID = "y6jn8c31"             # vlscppe 白名单机构号
INSTANCE_ID = "560dc9f3-1aa5-4a2f-b63c-9e18f8d0e175"

# 产品页：用于动态枚举可选的版本（edition）
PRODUCTS = [
    ("Windows 11", "windows11"),
    ("Windows 10", "windows10ISO"),
]


class MSDLError(Exception):
    pass


_LINK_CACHE = {}   # (product_slug, sku) -> (timestamp, links)


def _jload(body):
    """微软部分接口返回的是被 JSON 再包一层的字符串。"""
    d = json.loads(body)
    if isinstance(d, str):
        d = json.loads(d)
    return d


def _err_of(d):
    for e in (d.get("Errors") or []):
        return e.get("Value") or e.get("Key") or "未知错误"
    vc = d.get("ValidationContainer")
    if isinstance(vc, dict):
        for e in (vc.get("Errors") or []):
            return e.get("Value") or "校验失败"
    return None


class MicrosoftISO(object):
    """封装微软官方下载接口的三步调用：握手 → 取版本语言 → 取直链。"""

    def __init__(self, locale="zh-CN", timeout=45):
        self.locale = locale
        self.timeout = timeout
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar()),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )

    # ---------- 底层 ----------
    def _get(self, url, accept="*/*", referer=None, timeout=None):
        headers = {
            "User-Agent": UA,
            "Accept": accept,
            "Accept-Language": "%s,zh;q=0.9,en;q=0.8" % self.locale,
        }
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(url, headers=headers)
        try:
            with self._opener.open(req, timeout=timeout or self.timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            raise MSDLError("微软接口返回 HTTP %s" % e.code)
        except urllib.error.URLError as e:
            raise MSDLError("网络不可达：%s" % e.reason)

    def new_session(self):
        """微软的下载接口要求 sessionID 先经 vlscppe + ov-df 白名单，否则被 Sentinel 拒绝。"""
        sid = "%08x-%04x-%04x-%04x-%012x" % (
            int.from_bytes(os.urandom(4), "big"),
            int.from_bytes(os.urandom(2), "big"),
            (int.from_bytes(os.urandom(2), "big") & 0x0FFF) | 0x4000,
            (int.from_bytes(os.urandom(2), "big") & 0x3FFF) | 0x8000,
            int.from_bytes(os.urandom(6), "big"),
        )
        self._get("https://vlscppe.microsoft.com/tags?org_id=%s&session_id=%s" % (ORG_ID, sid))
        mdt = self._get("https://ov-df.microsoft.com/mdt.js?instanceId=%s&PageId=si&session_id=%s"
                        % (INSTANCE_ID, sid))
        w = (re.search(r"[?&]w=([A-F0-9]+)", mdt) or [None, None])[1]
        rticks = (re.search(r'rticks="\+?(\d+)', mdt) or [None, None])[1]
        if not (w and rticks):
            raise MSDLError("微软风控握手失败（mdt.js 未返回参数）")
        self._get("https://ov-df.microsoft.com/?session_id=%s&CustomerId=%s&PageId=si&w=%s&mdt=%d&rticks=%s"
                  % (sid, INSTANCE_ID, w, int(time.time() * 1000), rticks))
        return sid

    def _referer(self, product_slug):
        return "https://www.microsoft.com/%s/software-download/%s" % (self.locale, product_slug)

    # ---------- 对外 ----------
    def editions(self, product_slug):
        """从产品页 HTML 里枚举 version（edition）列表，返回 [(id, 名称)]。"""
        html = self._get(self._referer(product_slug), accept="text/html")
        # 只取 product-edition 下拉框里的 option
        block = html
        m = re.search(r'<select[^>]+id="product-edition"[^>]*>(.*?)</select>', html, re.S)
        if m:
            block = m.group(1)
        opts = re.findall(r'<option[^>]+value="(\d+)"[^>]*>([^<]{2,160})</option>', block)
        if not opts:
            opts = re.findall(r'<option[^>]+value="(\d+)"[^>]*>([^<]{2,160})</option>', html)
        out, seen = [], set()
        for vid, label in opts:
            if vid in seen:
                continue
            seen.add(vid)
            label = re.sub(r"\s+", " ", label).strip()
            out.append((vid, label))
        return out

    def languages(self, edition_id, product_slug="windows11"):
        """返回该版本下所有语言，元素为 dict(sku, language, localized, build)。"""
        last = None
        for attempt in range(3):
            sid = self.new_session()
            url = ("%s/getskuinformationbyproductedition?profile=%s&productEditionId=%s"
                   "&SKU=undefined&friendlyFileName=undefined&Locale=%s&sessionID=%s"
                   % (API, PROFILE_ID, edition_id, "en-US", sid))
            d = _jload(self._get(url, accept="application/json",
                                 referer=self._referer(product_slug)))
            err = _err_of(d)
            if err:
                last = err
                if "Sentinel" in err and attempt < 2:
                    time.sleep(3 + attempt * 3)
                    continue
                raise MSDLError(self._friendly(err))
            rows = []
            for s in d.get("Skus") or []:
                rows.append({
                    "sku": str(s.get("Id")),
                    "language": s.get("Language") or "",
                    "localized": s.get("LocalizedLanguage") or s.get("Language") or "",
                    "build": s.get("ProductDisplayName") or "",
                })
            self._last_session = sid
            return rows
        raise MSDLError(self._friendly(last or "未知错误"))

    def links(self, sku, product_slug="windows11", session_id=None, use_cache=True):
        """返回 [(下载类型, 直链)]，直链有效期通常 24 小时。

        命中 Sentinel 风控时自动换一个新 session 重试；同一 SKU 短期内复用已取到的直链，
        避免用户连点导致被微软限流。
        """
        key = (product_slug, str(sku))
        if use_cache:
            hit = _LINK_CACHE.get(key)
            if hit and time.time() - hit[0] < 600:
                return hit[1]

        sid = session_id or self.new_session()
        last = None
        for attempt in range(3):
            url = ("%s/GetProductDownloadLinksBySku?profile=%s&productEditionId=undefined&SKU=%s"
                   "&friendlyFileName=undefined&Locale=%s&sessionID=%s"
                   % (API, PROFILE_ID, sku, "en-US", sid))
            d = _jload(self._get(url, accept="application/json",
                                 referer=self._referer(product_slug)))
            err = _err_of(d)
            if err:
                last = err
                if "Sentinel" in err and attempt < 2:
                    time.sleep(3 + attempt * 3)
                    sid = self.new_session()
                    continue
                raise MSDLError(self._friendly(err))
            out = []
            for o in d.get("ProductDownloadOptions") or []:
                uri = o.get("Uri")
                if uri:
                    out.append((str(o.get("DownloadType")), uri))
            if not out:
                raise MSDLError("微软未返回下载链接")
            _LINK_CACHE[key] = (time.time(), out)
            self._last_session = sid
            return out
        raise MSDLError(self._friendly(last or "未知错误"))

    @staticmethod
    def _friendly(err):
        if "Sentinel" in err:
            return "微软风控拒绝了本次请求（Sentinel）。通常是因为短时间内请求过多，等待几分钟后再试。"
        if "715-123130" in err:
            return "当前 IP 已被微软限制下载（错误码 715-123130），请更换网络后重试。"
        return "微软接口报错：%s" % err


# --------------------------------------------------------------------------
# 下载器：多线程分段 + 断点续传（微软 CDN 支持 Range）
# --------------------------------------------------------------------------
class Downloader(object):
    def __init__(self, url, dest, threads=8, chunk=4 * 1024 * 1024):
        self.url = url
        self.dest = dest
        self.threads = max(1, int(threads))
        self.chunk = chunk
        self.total = 0
        self.resumable = False
        self.filename = os.path.basename(dest)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.error = None
        self.finished = False
        self._workers = []
        self._meta = dest + ".msdl.json"

    # ---------- 探测 ----------
    def set_dest(self, dest):
        self.dest = dest
        self.filename = os.path.basename(dest)
        self._meta = dest + ".msdl.json"

    def probe(self):
        info = {}
        hdrs = {"User-Agent": UA}
        try:
            req = urllib.request.Request(self.url, method="HEAD", headers=hdrs)
            with urllib.request.urlopen(req, timeout=30,
                                        context=ssl.create_default_context()) as r:
                hdrs_out = r.headers
                info["status"] = r.status
        except Exception:
            hdrs_out = None
            info["status"] = None

        if hdrs_out is None:
            # 有些 CDN 不响应 HEAD，退化为 1 字节 Range 探测
            req = urllib.request.Request(self.url, headers=dict(hdrs, Range="bytes=0-0"))
            with urllib.request.urlopen(req, timeout=30,
                                        context=ssl.create_default_context()) as r:
                hdrs_out = r.headers
                info["status"] = r.status

        cl = hdrs_out.get("Content-Length")
        cr = hdrs_out.get("Content-Range")
        info["content_length"] = int(cl) if cl and cl.isdigit() else 0
        info["accept_ranges"] = (hdrs_out.get("Accept-Ranges") or "") in ("bytes", "Bytes")
        info["content_range"] = cr
        if cr and "/" in cr:
            tail = cr.rsplit("/", 1)[-1]
            if tail.isdigit():
                info["content_length"] = int(tail)
        cd = hdrs_out.get("Content-Disposition") or ""
        m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, re.I)
        if m:
            info["filename"] = urllib.parse.unquote(m.group(1)).strip()

        self.total = info["content_length"]
        self.resumable = info["accept_ranges"]
        self.probe_info = info
        return info

    # ---------- 进度 ----------
    def downloaded(self):
        if self.finished and os.path.exists(self.dest):
            return os.path.getsize(self.dest)
        n = 0
        for p in self._part_paths():
            try:
                n += os.path.getsize(p)
            except OSError:
                pass
        return n

    def _part_paths(self):
        return [self.dest + ".part%d" % i for i in range(self.threads)]

    # ---------- 主流程 ----------
    def _segments(self):
        n = self.threads if (self.resumable and self.total > 32 * 1024 * 1024) else 1
        seg = []
        if n <= 1:
            seg.append((0, self.total - 1 if self.total else -1))
            return seg
        size = self.total // n
        for i in range(n):
            start = i * size
            end = (self.total - 1) if i == n - 1 else (start + size - 1)
            seg.append((start, end))
        return seg

    def _wipe_parts(self):
        for p in self._part_paths():
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.remove(self._meta)
        except OSError:
            pass

    def start(self):
        if not getattr(self, "probe_info", None):
            self.probe()
        segs = self._segments()
        # 保证 part 文件数量与分段一致
        if len(segs) != self.threads:
            self.threads = len(segs)
        # 旧的续传信息如果与本次大小/分段数不符，直接作废，避免拼接出错
        if os.path.exists(self._meta):
            try:
                with open(self._meta, "r", encoding="utf-8") as f:
                    old = json.load(f)
                if old.get("total") != self.total or len(old.get("segments") or []) != len(segs):
                    self._wipe_parts()
            except (OSError, ValueError):
                self._wipe_parts()
        self._save_meta(segs)
        for i, (a, b) in enumerate(segs):
            t = threading.Thread(target=self._run_segment, args=(i, a, b), daemon=True)
            t.start()
            self._workers.append(t)
        threading.Thread(target=self._join_all, daemon=True).start()

    def _save_meta(self, segs):
        try:
            with open(self._meta, "w", encoding="utf-8") as f:
                json.dump({
                    "url": self.url,
                    "total": self.total,
                    "segments": segs,
                    "dest": self.dest,
                }, f)
        except OSError:
            pass

    def _run_segment(self, idx, a, b):
        path = self.dest + ".part%d" % idx
        have = os.path.getsize(path) if os.path.exists(path) else 0
        if b >= 0 and have > (b - a + 1):
            have = 0          # 分片异常偏大，重来
            try:
                os.remove(path)
            except OSError:
                pass
        pos = a + have
        if not os.path.exists(path):
            pos = a
        if b >= 0 and pos > b:
            return
        attempt = 0
        while not self._stop.is_set():
            try:
                headers = {"User-Agent": UA}
                if b >= 0:
                    headers["Range"] = "bytes=%d-%d" % (pos, b)
                else:
                    headers["Range"] = "bytes=%d-" % pos
                req = urllib.request.Request(self.url, headers=headers)
                with urllib.request.urlopen(req, timeout=60,
                                            context=ssl.create_default_context()) as r:
                    if b >= 0 and r.status != 206 and pos > a:
                        # 服务端忽略了 Range：从头覆盖，避免拼接错乱
                        pos, have = a, 0
                        path = self.dest + ".part%d" % idx
                    mode = "ab" if (pos > a and os.path.exists(path)) else "wb"
                    with open(path, mode) as f:
                        while not self._stop.is_set():
                            buf = r.read(256 * 1024)
                            if not buf:
                                break
                            f.write(buf)
                            pos += len(buf)
                            if b >= 0 and pos > b:
                                break
                if b < 0 or pos >= b:
                    return
                attempt = 0
            except Exception as e:
                if self._stop.is_set():
                    return
                attempt += 1
                if attempt > 6:
                    with self._lock:
                        self.error = "第 %d 个分段失败：%s" % (idx + 1, e)
                    return
                time.sleep(min(2 * attempt, 10))
                try:
                    pos = a + os.path.getsize(path)
                except OSError:
                    pos = a

    def _join_all(self):
        for t in self._workers:
            t.join()
        if self._stop.is_set():
            return
        if self.error:
            return
        try:
            with open(self.dest, "wb") as out:
                for p in self._part_paths():
                    if not os.path.exists(p):
                        continue
                    with open(p, "rb") as f:
                        while True:
                            buf = f.read(1024 * 1024)
                            if not buf:
                                break
                            out.write(buf)
            for p in self._part_paths():
                try:
                    os.remove(p)
                except OSError:
                    pass
            try:
                os.remove(self._meta)
            except OSError:
                pass
            self.finished = True
        except OSError as e:
            self.error = "合并分段失败：%s" % e

    def stop(self):
        self._stop.set()


def sha256_file(path, cb=None, stop_flag=None):
    h = hashlib.sha256()
    size = os.path.getsize(path)
    done = 0
    with open(path, "rb") as f:
        while True:
            buf = f.read(4 * 1024 * 1024)
            if not buf:
                break
            h.update(buf)
            done += len(buf)
            if cb:
                cb(done, size)
            if stop_flag is not None and stop_flag.is_set():
                return None
    return h.hexdigest()


def human(n):
    if n is None:
        return "-"
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return ("%.2f %s" % (n, u)) if u != "B" else ("%d B" % n)
        n /= 1024.0
    return "%.2f TB" % n
