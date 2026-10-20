# -*- coding: utf-8 -*-
"""诊断 Win11 直链的 Sentinel 拒绝：变体 A=先访问页面+zh-CN；B=en-US 重试"""
import sys, time
sys.path.insert(0, r"D:\msdl")
import msdl_core as C

api = C.MicrosoftISO(locale="zh-CN")

def variant(label, locale, visit_page):
    try:
        if visit_page:
            api._get(api._referer("windows11"), accept="text/html")
        sid = api.new_session()
        time.sleep(2)
        links = api.links(27157, "windows11", session_id=sid, use_cache=False)
        print(f"[{label}] OK -> {links[0][1][:80]}")
        return True
    except Exception as e:
        print(f"[{label}] FAIL: {e}")
        return False

ok = variant("A 先访问页面 + en-US", "en-US", True)
if not ok:
    time.sleep(20)
    ok = variant("B 再试", "en-US", False)
print("结论:", "Win11 链路恢复" if ok else "仍被限流")
