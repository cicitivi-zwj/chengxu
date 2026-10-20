# -*- coding: utf-8 -*-
"""GUI 冒烟测试：无人工交互启动窗口，跑 12 秒，导出控件状态与日志"""
import sys, time, os
sys.path.insert(0, r"D:\msdl")
import tkinter as tk
import msdl

root = tk.Tk()
app = msdl.App(root)
t0 = time.time()
deadline = t0 + 14
while time.time() < deadline:
    root.update()
    time.sleep(0.03)

print("=== 产品下拉 ===", app.cb_product.get())
print("=== 版本下拉 ===", app.cb_edition.get(), "| 候选:", list(app.cb_edition.cget("values")))
print("=== 语言下拉 ===", app.cb_lang.get(), "| 数量:", len(app.cb_lang.cget("values")))
print("=== 查询状态 ===", app.lbl_query.cget("text"))
print("=== 按钮状态 ===", "query=", app.btn_query.cget("state"), "dl=", app.btn_dl.cget("state"))
print("=== 日志 ===")
print(app.log.get("1.0", "end").strip())
root.destroy()
