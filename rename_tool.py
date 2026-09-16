#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量改名工具 —— 删除文件名中「第一个字符」与「第二个字符」之间的内容（连同这两个字符本身）。

流程：
  1) 对话框选择文件夹；
  2) 对话框输入第一个字符（串）；
  3) 对话框输入第二个字符（串）；
  4) 递归查找文件名里同时含有这两个字符的文件；
  5) 改名：把每一对「第一个字符 … 第二个字符」连同两端一起删掉。
     一个文件名里有多对时，从左到右把所有不重叠的配对全部删掉；
     只在主文件名范围内删，扩展名保持不变（以最后一个点号分界）。
  6) 改名后若与已有文件重名，直接用改名结果覆盖它（后面的覆盖前面的）。

关于「覆盖」：
  - 覆盖不可逆。所以程序会先给出完整预览，单独统计会覆盖掉多少个文件，
    并额外弹一次确认；
  - 「后面的」定义：按「所在目录 → 原文件名」排序后靠后的那个。同一目录里
    若多个文件改名后撞成同一个名字，只有排序最后的那次结果会留下；
  - 每次执行都写入日志，便于追溯。

自测：python rename_tool.py --selftest
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

APP_TITLE = "批量改名：删除两字符之间的内容"
LOG_NAME = "rename_tool_log.txt"

STATUS_RENAME = "rename"        # 直接改名
STATUS_OVERWRITE = "overwrite"  # 改名，并覆盖掉一个原本就存在的同名文件
STATUS_COVERED = "covered"      # 改名，但结果会被后面某个文件覆盖（内容留不下）
STATUS_SKIP = "skip"            # 新主名为空，跳过


# ======================================================================
# 核心逻辑（纯函数，可单测）
# ======================================================================

def collapse_once(text: str, first: str, second: str) -> tuple[str, bool]:
    """删除 text 中最先出现的一对：first 的首次出现 到 其后 second 的首次出现（含两端）。

    找不到配对就原样返回，第二个返回值为 False。
    """
    i = text.find(first)
    if i < 0:
        return text, False
    j = text.find(second, i + len(first))
    if j < 0:
        return text, False
    return text[:i] + text[j + len(second):], True


def new_stem(stem: str, first: str, second: str) -> str:
    """反复删除所有不重叠的配对，直到再也找不到为止。

    每删一次至少缩短 len(first) + len(second) >= 2 个字符，因此必然终止。
    """
    if not first or not second:
        raise ValueError("两个待删除的字符都不能为空")
    out = stem
    while True:
        out, changed = collapse_once(out, first, second)
        if not changed:
            return out


def split_name(filename: str) -> tuple[str, str]:
    """拆成 (主名, 扩展名)。以最后一个点号分界，隐藏文件视为没有扩展名。"""
    p = Path(filename)
    return p.stem, p.suffix


@dataclass
class PlanItem:
    """一条改名记录。"""

    directory: Path
    old_name: str
    new_name: str
    status: str
    target_exists: bool = False   # 新名字已经被同目录下另一个文件占用
    covered_by: str = ""          # 结果稍后会被哪个文件覆盖（空 = 自己留下）

    @property
    def old_path(self) -> Path:
        return self.directory / self.old_name

    @property
    def new_path(self) -> Path:
        return self.directory / self.new_name

    @property
    def survives(self) -> bool:
        """这次改名产生的内容最终是否留得下来。"""
        return self.status != STATUS_SKIP and not self.covered_by

    def describe(self) -> str:
        if self.status == STATUS_SKIP:
            return "跳过：新主名为空"
        if self.covered_by:
            return f"改名后会被「{self.covered_by}」覆盖"
        if self.status == STATUS_OVERWRITE:
            return "改名，覆盖已存在的同名文件"
        return "改名"


@dataclass
class ScanStats:
    """扫描统计 —— 用来证明子文件夹确实被翻到了最后一层。"""

    dirs_visited: int = 0
    max_depth: int = 0
    unreadable: list[str] = field(default_factory=list)

    def summary(self) -> str:
        text = f"已扫描 {self.dirs_visited} 个文件夹（递归所有层级的子文件夹，最深第 {self.max_depth} 层）"
        if self.unreadable:
            text += f"；其中 {len(self.unreadable)} 个文件夹无法访问，已跳过"
        return text


def scan(root: str | os.PathLike[str], first: str, second: str) -> tuple[list[PlanItem], ScanStats]:
    """递归扫描 root 及其所有层级的子文件夹，生成改名计划。

    计划按「目录 → 原文件名」排序，该次序就是执行次序。
    """
    root_path = Path(root)
    stats = ScanStats()
    raw: list[tuple[Path, str, str, str]] = []  # (目录, 原文件名, 新主名, 新文件名)

    def on_error(exc: OSError) -> None:
        name = getattr(exc, "filename", None)
        stats.unreadable.append(str(name) if name else str(exc))

    for dirpath, dirnames, filenames in os.walk(root_path, onerror=on_error):
        stats.dirs_visited += 1
        try:
            depth = len(Path(dirpath).relative_to(root_path).parts)
        except ValueError:
            depth = 0
        if depth > stats.max_depth:
            stats.max_depth = depth

        # 不跟随符号链接目录，免得绕圈或跑到别处去
        dirnames[:] = sorted(d for d in dirnames if not os.path.islink(os.path.join(dirpath, d)))
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            if os.path.islink(full):
                continue
            stem, suffix = split_name(fn)
            ns = new_stem(stem, first, second)
            if ns != stem:
                raw.append((Path(dirpath), fn, ns, ns + suffix))

    # 「前面的 / 后面的」= 排序后靠前 / 靠后
    raw.sort(key=lambda r: (str(r[0]).lower(), r[1].lower()))

    existing_cache: dict[Path, set[str]] = {}

    def existing(d: Path) -> set[str]:
        if d not in existing_cache:
            try:
                existing_cache[d] = {os.path.normcase(n) for n in os.listdir(d)}
            except OSError:
                existing_cache[d] = set()
        return existing_cache[d]

    # 某个目标名最终归谁：同一目录下最后一个改到该名字的文件
    keeper: dict[tuple[Path, str], str] = {}
    for d, old, _ns, new in raw:
        keeper[(d, os.path.normcase(new))] = old

    planned = {(d, os.path.normcase(old)) for d, old, _ns, _new in raw}

    items: list[PlanItem] = []
    for d, old, ns, new in raw:
        if ns == "":
            items.append(PlanItem(d, old, new, STATUS_SKIP))
            continue

        key = (d, os.path.normcase(new))
        winner = keeper[key]
        covered_by = "" if winner == old else winner
        # 目标名已被占用，且占用者不在本计划里（它不会让位）→ 真会覆盖掉一个已有文件
        target_exists = (
            os.path.normcase(new) in existing(d)
            and (d, os.path.normcase(new)) not in planned
            and os.path.normcase(new) != os.path.normcase(old)
        )

        if covered_by:
            status = STATUS_COVERED
        elif target_exists:
            status = STATUS_OVERWRITE
        else:
            status = STATUS_RENAME

        items.append(PlanItem(d, old, new, status, target_exists, covered_by))

    return items, stats


def execute(items: list[PlanItem]) -> list[tuple[PlanItem, bool, str]]:
    """按计划顺序执行改名，返回 (记录, 是否成功, 说明)。

    用 os.replace 而不是 os.rename —— 前者在目标已存在时直接覆盖，
    这正是「后面的覆盖前面的」所需要的。
    """
    results: list[tuple[PlanItem, bool, str]] = []
    for it in items:
        if it.status == STATUS_SKIP:
            results.append((it, False, "跳过：新主名为空"))
            continue

        replaced = it.new_path.exists()
        try:
            os.replace(it.old_path, it.new_path)
        except OSError as exc:
            results.append((it, False, f"{type(exc).__name__}: {exc}"))
        else:
            note = "覆盖了同名文件" if replaced else ""
            results.append((it, True, note))
    return results


# ======================================================================
# 日志
# ======================================================================

def log_line(message: str) -> None:
    """写一条带时间戳的诊断信息（界面卡住时，最后一行就是卡住的位置）。"""
    try:
        with (Path.home() / LOG_NAME).open("a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}\n")
    except OSError:
        pass


def write_log(lines: list[str]) -> Path | None:
    try:
        path = Path.home() / LOG_NAME
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return path
    except OSError:
        return None


# ======================================================================
# 图形界面
# ======================================================================

def run_gui() -> int:
    log_line(f"=== 启动界面（解释器：{sys.executable}）===")

    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk

    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    root.withdraw()
    log_line("主窗口就绪，准备弹出「选择文件夹」对话框")

    # ---- 步骤 1：选文件夹 ----
    folder = filedialog.askdirectory(title="第 1 步 / 共 3 步：请选择要处理的文件夹", parent=root)
    log_line(f"文件夹选择返回：{folder!r}")
    if not folder:
        return 0

    # ---- 步骤 2、3：输入两个字符 ----
    first = simpledialog.askstring(APP_TITLE, "第 2 步 / 共 3 步：请输入第一个字符（串）：", parent=root)
    log_line(f"第一个字符：{first!r}")
    if first is None:
        return 0

    second = simpledialog.askstring(APP_TITLE, "第 3 步 / 共 3 步：请输入第二个字符（串）：", parent=root)
    log_line(f"第二个字符：{second!r}")
    if second is None:
        return 0

    if not first or not second:
        messagebox.showerror(APP_TITLE, "两个字符都不能为空，程序退出。", parent=root)
        return 1

    # ---- 扫描 ----
    try:
        items, stats = scan(folder, first, second)
    except ValueError as exc:
        messagebox.showerror(APP_TITLE, str(exc), parent=root)
        return 1

    todo = [it for it in items if it.status != STATUS_SKIP]
    n_overwrite = sum(1 for it in todo if it.target_exists)
    n_covered = sum(1 for it in todo if it.covered_by)
    n_survive = sum(1 for it in todo if it.survives)
    log_line(
        f"{stats.summary()}；可改名 {len(todo)} 个；覆盖已存在文件 {n_overwrite} 个；"
        f"被后面结果覆盖 {n_covered} 个；最终留下 {n_survive} 个"
    )

    if not todo:
        messagebox.showinfo(
            APP_TITLE,
            f"没有找到可改名的文件。\n\n文件夹：{folder}\n{stats.summary()}\n"
            f"删除区间：“{first}” … “{second}”",
            parent=root,
        )
        return 0

    # ---- 预览确认 ----
    win = tk.Toplevel(root)
    win.title(f"{APP_TITLE} － 请核对下表，然后点「执行改名」")
    win.minsize(760, 400)
    # 主窗口是隐藏的（withdraw），光靠 transient 不足以让这个窗口露面：
    # 显式居中，再顶到最前，否则它可能被控制台窗口挡在背后，看着像「没反应」。
    width, height = 1000, 600
    win.update_idletasks()
    pos_x = max(0, (win.winfo_screenwidth() - width) // 2)
    pos_y = max(0, (win.winfo_screenheight() - height) // 3)
    win.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    outer = ttk.Frame(win, padding=12)
    outer.pack(fill="both", expand=True)

    ttk.Label(
        outer,
        text=(
            f"文件夹：{folder}\n"
            f"规则：删除 “{first}” 与 “{second}” 之间（含这两个字符）的全部内容，扩展名不变；"
            f"查找范围含所有层级的子文件夹。\n"
            f"{stats.summary()}"
        ),
        justify="left",
        wraplength=960,
    ).pack(anchor="w")

    ttk.Label(
        outer,
        text=(
            f"共 {len(todo)} 个文件将改名　→　最终留下 {n_survive} 个"
            + (f"；{n_covered} 个会被后面的结果覆盖" if n_covered else "")
            + (f"；{n_overwrite} 个会覆盖掉已存在的同名文件" if n_overwrite else "")
        ),
        justify="left",
        wraplength=960,
    ).pack(anchor="w", pady=(4, 0))

    if n_overwrite or n_covered:
        ttk.Label(
            outer,
            text=f"⚠ 本次操作会永久覆盖 {n_overwrite + n_covered} 个文件的内容，被覆盖的内容无法恢复。请先核对下表。",
            justify="left",
            wraplength=960,
            foreground="#b00020",
        ).pack(anchor="w", pady=(6, 0))

    body = ttk.Frame(outer)
    body.pack(fill="both", expand=True, pady=(10, 0))

    columns = ("rel", "old", "new", "note")
    tree = ttk.Treeview(body, columns=columns, show="headings", height=min(len(items), 18), selectmode="browse")
    tree.heading("rel", text="所在子文件夹")
    tree.heading("old", text="原文件名")
    tree.heading("new", text="新文件名")
    tree.heading("note", text="说明")
    tree.column("rel", width=200, anchor="w")
    tree.column("old", width=280, anchor="w")
    tree.column("new", width=280, anchor="w")
    tree.column("note", width=220, anchor="w")

    vsb = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    tree.tag_configure("overwrite", foreground="#b00020")
    tree.tag_configure("skip", foreground="#808080")

    for it in items:
        rel = os.path.relpath(it.directory, folder)
        rel = "" if rel == "." else rel
        if it.status == STATUS_SKIP:
            tag = ("skip",)
        elif it.covered_by or it.status == STATUS_OVERWRITE:
            tag = ("overwrite",)
        else:
            tag = ()
        tree.insert("", "end", values=(rel, it.old_name, it.new_name, it.describe()), tags=tag)

    state = {"go": False}

    def on_execute() -> None:
        if n_overwrite or n_covered:
            if not messagebox.askyesno(
                APP_TITLE,
                f"确认要执行吗？\n\n"
                f"会有 {n_overwrite + n_covered} 个文件被永久覆盖，内容无法恢复。",
                parent=win,
            ):
                return
        state["go"] = True
        win.destroy()

    btns = ttk.Frame(outer)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="取消", command=win.destroy).pack(side="right", padx=(8, 0))
    exec_btn = ttk.Button(btns, text=f"执行改名（{len(todo)} 个）", command=on_execute)
    exec_btn.pack(side="right")

    def ensure_front() -> None:
        """再抬一次 —— 防止刚弹出的控制台窗口把预览窗口盖到后面去。"""
        try:
            win.lift()
            win.focus_force()
        except tk.TclError:
            pass

    def drop_topmost() -> None:
        try:
            win.attributes("-topmost", False)
        except tk.TclError:
            pass

    win.deiconify()
    win.lift()
    win.attributes("-topmost", True)
    win.update_idletasks()
    win.focus_force()
    win.after(800, ensure_front)
    win.after(1500, drop_topmost)
    win.grab_set()
    log_line(f"预览窗口已显示于 {pos_x},{pos_y}（{len(items)} 行），等待用户确认")
    win.wait_window()

    if not state["go"]:
        log_line("用户取消，未做任何改动")
        return 0
    log_line(f"用户确认执行，开始改名 {len(todo)} 个")

    # ---- 执行 ----
    results = execute(items)
    done = [r for r in results if r[1]]
    failed = [r for r in results if not r[1] and r[0].status != STATUS_SKIP]
    skipped = [r for r in results if not r[1] and r[0].status == STATUS_SKIP]

    lines = [f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 文件夹={folder} 删除区间 '{first}' .. '{second}'"]
    for it, success, note in results:
        if success:
            suffix = f"  [{note}]" if note else ""
            lines.append(f"  OK    {it.old_path}  ->  {it.new_name}{suffix}")
        else:
            lines.append(f"  SKIP  {it.old_path}  ({note})")
    log_path = write_log(lines)
    log_line(f"执行完成：成功 {len(done)}，失败 {len(failed)}，跳过 {len(skipped)}")

    summary = f"改名完成。\n\n成功 {len(done)} 个\n失败 {len(failed)} 个\n跳过 {len(skipped)} 个"
    if failed:
        summary += "\n\n失败明细：\n  " + "\n  ".join(f"{it.old_name}：{note}" for it, _ok, note in failed[:8])
    if log_path:
        summary += f"\n\n日志已追加到：\n{log_path}"
    messagebox.showinfo(APP_TITLE, summary, parent=root)

    return 0


# ======================================================================
# 自测
# ======================================================================

def selftest() -> int:
    import tempfile

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    failures: list[str] = []
    checks = [0]

    def check(label: str, got: object, want: object) -> None:
        checks[0] += 1
        if got != want:
            failures.append(f"{label}\n    got : {got!r}\n    want: {want!r}")

    # --- 删除规则 ---
    check("删第一对", new_stem("aXbYc", "X", "Y"), "ac")
    check("多对全删", new_stem("aXbYcXdY", "X", "Y"), "ac")
    check("相邻配对", new_stem("XaYXbY", "X", "Y"), "")
    check("三连", new_stem("aXbYcXdYeXfY", "X", "Y"), "ace")
    check("顺序颠倒不动", new_stem("aYbXc", "X", "Y"), "aYbXc")
    check("只缺第二个", new_stem("aXbc", "X", "Y"), "aXbc")
    check("只缺第一个", new_stem("abYc", "X", "Y"), "abYc")
    check("两字符相同", new_stem("a-b-c", "-", "-"), "ac")
    check("结果为空", new_stem("XabcY", "X", "Y"), "")
    check("多字符配对", new_stem("a<<b>>c<<d>>e", "<<", ">>"), "ace")
    check("多字符不成对", new_stem("a<<b>c", "<<", ">>"), "a<<b>c")
    check("无字符", new_stem("plain", "X", "Y"), "plain")

    # --- 拆名 ---
    check("拆名 a.b.txt", split_name("a.b.txt"), ("a.b", ".txt"))
    check("拆名 .gitignore", split_name(".gitignore"), (".gitignore", ""))
    check("拆名 无扩展名", split_name("readme"), ("readme", ""))
    check("拆名 中文", split_name("报告X草Y稿.docx"), ("报告X草Y稿", ".docx"))

    # --- 文件系统：多层级子文件夹必须一直翻到最后一层 ---
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        deep = base / "l1" / "l2" / "l3" / "l4"
        deep.mkdir(parents=True)
        (base / "aXbYz.txt").write_text("第 0 层", encoding="utf-8")
        (base / "l1" / "cXdYf.txt").write_text("第 1 层", encoding="utf-8")
        (deep / "eXfYh.txt").write_text("第 4 层", encoding="utf-8")

        deep_items, deep_stats = scan(base, "X", "Y")
        check("多层级都找到", sorted(it.new_name for it in deep_items), ["az.txt", "cf.txt", "eh.txt"])
        check("访问过的文件夹数", deep_stats.dirs_visited, 5)
        check("最深层级", deep_stats.max_depth, 4)
        check("没有不可访问项", deep_stats.unreadable, [])

        execute(deep_items)
        check("第 0 层改名", (base / "az.txt").read_text(encoding="utf-8"), "第 0 层")
        check("第 1 层改名", (base / "l1" / "cf.txt").read_text(encoding="utf-8"), "第 1 层")
        check("第 4 层改名", (deep / "eh.txt").read_text(encoding="utf-8"), "第 4 层")
        check("多层原文件已消失", (deep / "eXfYh.txt").exists(), False)

    # --- 文件系统：重名覆盖 ---
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "sub").mkdir()
        # 排序后 aXbYc.txt 在前、aXdYc.txt 在后，两者都想叫 ac.txt，
        # 而 ac.txt 本来就在 —— 最终 ac.txt 的内容应来自 aXdYc.txt
        (base / "ac.txt").write_text("原有的 ac", encoding="utf-8")
        (base / "aXbYc.txt").write_text("来自 aXbYc", encoding="utf-8")
        (base / "aXdYc.txt").write_text("来自 aXdYc", encoding="utf-8")
        (base / "sub" / "cXdY.md").write_text("子目录", encoding="utf-8")
        (base / "plain.txt").write_text("无关", encoding="utf-8")
        (base / "XabcY.txt").write_text("会变空名", encoding="utf-8")

        items, _st = scan(base, "X", "Y")
        got = sorted((it.old_name, it.new_name, it.status, it.covered_by) for it in items)
        want = sorted([
            ("aXbYc.txt", "ac.txt", STATUS_COVERED, "aXdYc.txt"),
            ("aXdYc.txt", "ac.txt", STATUS_OVERWRITE, ""),
            ("cXdY.md", "c.md", STATUS_RENAME, ""),
            ("XabcY.txt", ".txt", STATUS_SKIP, ""),
        ])
        check("扫描计划", got, want)

        results = execute(items)
        check("执行无异常", all(ok or it.status == STATUS_SKIP for it, ok, _ in results), True)

        check("ac.txt 存在", (base / "ac.txt").is_file(), True)
        check("ac.txt 是后面的胜出", (base / "ac.txt").read_text(encoding="utf-8"), "来自 aXdYc")
        check("aXbYc.txt 已消失", (base / "aXbYc.txt").exists(), False)
        check("aXdYc.txt 已消失", (base / "aXdYc.txt").exists(), False)
        check("子目录改名成功", (base / "sub" / "c.md").read_text(encoding="utf-8"), "子目录")
        check("空名文件被跳过", (base / "XabcY.txt").is_file(), True)
        check("无关文件保留", (base / "plain.txt").is_file(), True)

    # --- 文件系统：目标不存在时就是普通改名 ---
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "aXbYc.txt").write_text("x", encoding="utf-8")
        items, _st2 = scan(base, "X", "Y")
        check("无冲突时状态", [it.status for it in items], [STATUS_RENAME])
        check("无冲突时存活", [it.survives for it in items], [True])
        execute(items)
        check("普通改名结果", (base / "ac.txt").is_file(), True)

    if failures:
        print(f"自测失败 {len(failures)} 项（共 {checks[0]} 项）：")
        for f in failures:
            print("  - " + f)
        return 1

    print(f"自测全部通过（{checks[0]} 项断言）")
    return 0


def main() -> int:
    if "--selftest" in sys.argv[1:]:
        return selftest()
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
