# -*- coding: utf-8 -*-
"""
家谱查询程序（命令行版）
用法：运行后按提示输入序号或命令查询。
数据存在同目录的 jiapu.xlsx 里（Excel 表格），改人名不用动这个程序。
注意：需要先装 openpyxl 这个库（程序靠它读 Excel）：pip install openpyxl
"""

import os
import sys

from datetime import datetime
from openpyxl import load_workbook

# 让 Windows 的黑窗口能正常显示中文
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 数据文件路径：和本程序放在同一个文件夹里
数据文件 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jiapu.xlsx")

# 也允许在命令行里临时指定：python jiapu.py 别的表.xlsx
if len(sys.argv) > 1:
    数据文件 = os.path.abspath(sys.argv[1])


# ---------- 第一步：把家谱数据读进内存 ----------

def 读取家谱():
    try:
        工作簿 = load_workbook(数据文件, data_only=True)
    except FileNotFoundError:
        print("找不到数据文件 jiapu.xlsx，请确认它和程序在同一个文件夹里。")
        sys.exit(1)

    if "成员" not in 工作簿.sheetnames:
        print("jiapu.xlsx 里没有名为「成员」的工作表，请检查表格。")
        sys.exit(1)

    表 = 工作簿["成员"]
    表头 = [格.value for 格 in 表[1]]  # 第一行是表头：编号、姓名、性别……

    成员列表 = []
    for 行 in 表.iter_rows(min_row=2, values_only=True):
        一条 = dict(zip(表头, 行))
        # 跳过姓名空白、连编号也没有的行（多半是误敲的空行）
        if not 一条.get("姓名") and not 一条.get("编号"):
            continue
        # Excel 里数字会被读成 1.0 这种带小数的样子，统一转回整数再转成文字
        def 规整(x):
            if x is None:
                return ""
            if isinstance(x, datetime):          # 日期格式的格子，统一写成 1925-03-08
                return x.strftime("%Y-%m-%d")
            if isinstance(x, float) and x == int(x):
                return str(int(x))
            return str(x).strip()
        成员列表.append({
            "编号": 规整(一条.get("编号")),
            "姓名": 规整(一条.get("姓名")),
            "性别": 规整(一条.get("性别")),
            # 代数要当数字用（比较、排序），单独转成整数
            "代数": int(float(一条.get("代数") or 0)),
            "父亲": 规整(一条.get("父亲")),
            "母亲": 规整(一条.get("母亲")),
            "配偶": 规整(一条.get("配偶")),
            "阳历出生": 规整(一条.get("阳历出生")),
            "阴历出生": 规整(一条.get("阴历出生")),
            "阳历去世": 规整(一条.get("阳历去世")),
            "阴历去世": 规整(一条.get("阴历去世")),
            "备注": 规整(一条.get("备注")),
        })

    # 家族名称：从「填写说明」表里找"家族名称"那一行，找不到就用"家谱"
    家族名称 = "家谱"
    if "填写说明" in 工作簿.sheetnames:
        for 行 in 工作簿["填写说明"].iter_rows(values_only=True):
            if 行 and 行[0] == "家族名称" and len(行) > 1 and 行[1]:
                家族名称 = str(行[1]).strip()
                break

    return {
        "家族名称": 家族名称,
        "成员": 成员列表,
    }


家谱 = 读取家谱()
成员 = 家谱["成员"]
按编号 = {p["编号"]: p for p in 成员}
最代数 = max((p["代数"] for p in 成员), default=1)


# ---------- 第二步：几个小工具 ----------

def 找到人(关键词):
    """按编号或姓名找人。找到多个同名的人时，让用户选一个。"""
    关键词 = 关键词.strip()
    if not 关键词:
        return None

    # 先试试是不是直接输入了编号
    if 关键词 in 按编号:
        return 按编号[关键词]

    # 再按姓名找
    匹配 = [p for p in 成员 if p["姓名"] == 关键词]
    if len(匹配) == 1:
        return 匹配[0]
    if len(匹配) > 1:
        print("有好几位叫「%s」的：" % 关键词)
        for i, p in enumerate(匹配, 1):
            print("  %d. 编号%s，第%s代（%s）" % (i, p["编号"], p["代数"], p["备注"] or "无备注"))
        选择 = input("请输入序号选人（直接回车取消）：").strip()
        if 选择.isdigit() and 1 <= int(选择) <= len(匹配):
            return 匹配[int(选择) - 1]
        print("已取消。")
    else:
        print("家谱里没有叫「%s」的人。" % 关键词)
    return None


def 取人(编号):
    """按编号取人，取不到返回 None。"""
    return 按编号.get(编号)


def 名字(编号):
    """把编号变成名字，方便显示。"""
    p = 取人(编号)
    return p["姓名"] if p else "（未知）"


def 人描述(编号):
    """显示一个人：查得到就显示名字，查不到就说清编号是错的。"""
    if not 编号:
        return "未填"
    p = 取人(编号)
    return p["姓名"] if p else "编号%s（表里没有这个人）" % 编号


def 拆分编号(文本):
    """把"11、21"这种写法拆成 ['11', '21']；顿号、逗号、斜杠、空格都认。"""
    if not 文本:
        return []
    文本 = str(文本)
    for 分隔 in "、，,/／;；":
        文本 = 文本.replace(分隔, ",")
    return [x.strip() for x in 文本.replace(" ", ",").split(",") if x.strip()]


def 配偶们(p):
    """这个人的配偶，按先后顺序。自己填的排前面，别人回指的补在后面。"""
    结果 = []
    for 编号 in 拆分编号(p["配偶"]):
        q = 取人(编号)
        if q and q["编号"] not in [x["编号"] for x in 结果]:
            结果.append(q)
    for q in 成员:
        if p["编号"] in 拆分编号(q["配偶"]) and q["编号"] not in [x["编号"] for x in 结果]:
            结果.append(q)
    return 结果


def 子女分组(p):
    """子女按"和哪一任生的"分堆，返回 (分组列表, 没说清另一位家长的子女)。"""
    所有 = [q for q in 成员 if q["父亲"] == p["编号"] or q["母亲"] == p["编号"]]
    分组 = []
    用过 = set()
    for s in 配偶们(p):
        这一门 = [q for q in 所有 if q["父亲"] == s["编号"] or q["母亲"] == s["编号"]]
        if 这一门:
            分组.append((s, 这一门))
            用过.update(q["编号"] for q in 这一门)
    剩下 = [q for q in 所有 if q["编号"] not in 用过]
    return 分组, 剩下


def 生卒详情(p):
    """生卒信息整理成两三行，没填的不显示。"""
    行们 = []
    出生 = []
    if p["阳历出生"]:
        出生.append("阳历 " + p["阳历出生"])
    if p["阴历出生"]:
        出生.append("阴历 " + p["阴历出生"])
    if 出生:
        行们.append("出生：" + "　".join(出生))
    去世 = []
    if p["阳历去世"]:
        去世.append("阳历 " + p["阳历去世"])
    if p["阴历去世"]:
        去世.append("阴历 " + p["阴历去世"])
    if 去世:
        行们.append("去世：" + "　".join(去世))
    return 行们


def 生卒简称(p):
    """列表里用的简短写法，比如 1872-1948 或 1949-（还在世）。"""
    def 取年(文本):
        if 文本[:4].isdigit():
            return 文本[:4]
        import re
        m = re.search(r"(1[6-9]\d{2}|20\d{2})", 文本)   # 阴历里若写了"1925年二月廿四"也能认出来
        return m.group(1) if m else ""
    生 = 取年(p["阳历出生"] or p["阴历出生"])
    去 = 取年(p["阳历去世"] or p["阴历去世"])
    if 生 and 去:
        return "%s-%s" % (生, 去)
    if 生:
        return "%s-" % 生
    if 去:
        return "?-%s" % 去
    return ""


def 数据体检():
    """开机自查一遍表格：编号、父母、配偶、代数有没有填错。只报问题，不拦着用。"""
    问题 = []
    编号表 = {}
    for p in 成员:
        if not p["编号"]:
            问题.append("%s 没填编号" % (p["姓名"] or "（有位没名字的人）"))
        编号表.setdefault(p["编号"], []).append(p["姓名"])
    for 编号, 名们 in 编号表.items():
        if 编号 and len(名们) > 1:
            问题.append("编号 %s 重复了 %d 次：%s" % (编号, len(名们), "、".join(名们)))
    for p in 成员:
        if p["代数"] <= 0:
            问题.append("%s 没填代数（第几代）" % p["姓名"])
        for 栏 in ("父亲", "母亲"):
            家长 = 取人(p[栏]) if p[栏] else None
            if p[栏] and not 家长:
                问题.append("%s 的%s填的是编号 %s，可表里没有这个人" % (p["姓名"], 栏, p[栏]))
            elif 家长 and p["代数"] and 家长["代数"] and p["代数"] != 家长["代数"] + 1:
                问题.append("%s（第%s代）和%s%s（第%s代）的代数是断的，检查一下"
                            % (p["姓名"], p["代数"], 栏, 家长["姓名"], 家长["代数"]))
        for 编号 in 拆分编号(p["配偶"]):
            if 编号 not in 按编号:
                问题.append("%s 的配偶填的是编号 %s，可表里没有这个人" % (p["姓名"], 编号))
    # 同一个人被两处当成孩子（父母都写了但两人不是夫妻）也提醒一下
    for p in 成员:
        if p["父亲"] in 按编号 and p["母亲"] in 按编号:
            父 = 取人(p["父亲"])
            母 = 取人(p["母亲"])
            if 母["编号"] not in [s["编号"] for s in 配偶们(父)] and 父["编号"] != 母["编号"]:
                问题.append("%s 的父母（%s、%s）在表里不是夫妻，确认一下"
                            % (p["姓名"], 父["姓名"], 母["姓名"]))
    return 问题


# ---------- 第三步：各项查询功能 ----------

def 查个人():
    关键词 = input("请输入要查的人名（或编号）：")
    p = 找到人(关键词)
    if not p:
        return
    print()
    print("─── %s ───" % p["姓名"])
    print("第 %s 代" % p["代数"])
    print("性别：%s" % (p["性别"] or "未填"))
    for 行 in 生卒详情(p):
        print(行)
    if p["父亲"]:
        print("父亲：%s" % 人描述(p["父亲"]))
    if p["母亲"]:
        print("母亲：%s" % 人描述(p["母亲"]))
    配们 = 配偶们(p)
    if len(配们) == 1:
        print("配偶：%s" % 配们[0]["姓名"])
    elif len(配们) > 1:
        print("配偶：" + "、".join("%s（第%d任）" % (s["姓名"], i) for i, s in enumerate(配们, 1)))
    婚组, 剩 = 子女分组(p)
    多任 = len(配们) > 1
    for s, 孩子们 in 婚组:
        if 多任:
            print("与%s的子女：%s" % (s["姓名"], "、".join(k["姓名"] for k in 孩子们)))
        else:
            print("子女：" + "、".join(k["姓名"] for k in 孩子们))
    if 剩:
        print("子女（另一位家长未记录）：" + "、".join(k["姓名"] for k in 剩))
    if p["备注"]:
        print("备注：%s" % p["备注"])
    print()


def 查祖先():
    关键词 = input("请输入要往上追的人名（或编号）：")
    p = 找到人(关键词)
    if not p:
        return
    print()
    print("%s 的直系祖先（从近到远，遇到分叉往父系走）：" % p["姓名"])
    当前 = p
    断在哪 = None
    while True:
        父 = 取人(当前["父亲"]) if 当前["父亲"] else None
        母 = 取人(当前["母亲"]) if 当前["母亲"] else None
        填了 = 当前["父亲"] or 当前["母亲"]          # 表里写了父母，只是查不到人 → 编号填错
        if not 父 and not 母:
            断在哪 = "填错" if 填了 else "没填"
            break
        if 父 and 母:
            print("  第%s代：%s（父）、%s（母）" % (父["代数"], 父["姓名"], 母["姓名"]))
            当前 = 父
        else:
            谁 = 父 or 母
            print("  第%s代：%s" % (谁["代数"], 谁["姓名"]))
            当前 = 谁
    if 当前["编号"] == p["编号"]:
        if 断在哪 == "填错":
            缺 = "、".join("编号" + x for x in (p["父亲"], p["母亲"]) if x and not 取人(x))
            print("  ⚠ 表里给%s填的父母是 %s，可表里没有这些人，往上追不下去了。" % (p["姓名"], 缺))
        else:
            print("  （家谱里没有记录他的父母，应该是这一支的开头）")
    elif 断在哪 == "填错":
        print("  ⚠ %s 的父母编号（%s）在表里找不到，就追到这里。" % (当前["姓名"], 当前["父亲"] or 当前["母亲"]))
    print()


def 查后代():
    关键词 = input("请输入要往下查的人名（或编号）：")
    p = 找到人(关键词)
    if not p:
        return
    print()
    print("%s 的后代：" % p["姓名"])
    配们 = 配偶们(p)
    多任 = len(配们) > 1
    见过 = set()          # 防止表格里填成环，转起来没完
    人数 = [0]

    def 哪一任(孩子):
        for s in 配们:
            if 孩子["父亲"] == s["编号"] or 孩子["母亲"] == s["编号"]:
                return s["姓名"]
        return None

    def 列后代(某人, 缩进):
        if 某人["编号"] in 见过:
            print("  " * 缩进 + "└─ %s（表格里的关系成了环，到此为止）" % 某人["姓名"])
            return
        见过.add(某人["编号"])
        子女 = [q for q in 成员 if q["父亲"] == 某人["编号"] or q["母亲"] == 某人["编号"]]
        for 孩子 in sorted(子女, key=lambda x: int(x["编号"])):
            标注 = ""
            if 多任 and 缩进 == 0:
                谁 = 哪一任(孩子)
                if 谁:
                    标注 = "（与%s所出）" % 谁
            print("  " * 缩进 + "└─ %s（第%s代）%s" % (孩子["姓名"], 孩子["代数"], 标注))
            人数[0] += 1
            列后代(孩子, 缩进 + 1)

    列后代(p, 0)
    if 人数[0] == 0:
        print("  （家谱里没有记录他的后代）")
    print()


def 按代列出():
    代 = input("请输入要看的代数（1 到 %d）：" % 最代数).strip()
    if not 代.isdigit():
        print("请输入数字，比如 3。")
        return
    结果 = [p for p in 成员 if p["代数"] == int(代)]
    if not 结果:
        print("第%s代没有记录。" % 代)
        return
    print()
    print("─── 第%s代，共%d人 ───" % (代, len(结果)))
    for p in sorted(结果, key=lambda x: int(x["编号"])):
        父母 = []
        if p["父亲"]:
            父母.append(名字(p["父亲"]))
        if p["母亲"]:
            父母.append(名字(p["母亲"]))
        提示 = ("（" + "/".join(父母) + "所出）") if 父母 else ""
        生卒 = 生卒简称(p)
        日期 = ("　" + 生卒) if 生卒 else ""
        print("  %s%s %s %s" % (p["姓名"], 日期, 提示, p["备注"] or ""))
    print()


def 列出全家():
    print()
    print("─── %s ───" % 家谱.get("家族名称", "家谱"))
    for 代数 in range(1, 最代数 + 1):
        结果 = [p for p in 成员 if p["代数"] == 代数]
        if 结果:
            print("第%s代：" % 代数 + "、".join(p["姓名"] for p in 结果))
    没代数 = [p for p in 成员 if p["代数"] <= 0]
    if 没代数:
        print("代数没填的人：" + "、".join(p["姓名"] for p in 没代数))
    print("共 %d 人。" % len(成员))
    print()


def 打印体检(自动=False):
    """把自查结果打出来。自动模式（开机时）没问题就不出声。"""
    问题 = 数据体检()
    if not 问题:
        if not 自动:
            print("表格自查通过，没发现问题。")
        return
    print()
    print("表格自查发现 %d 处需要留意：" % len(问题))
    for q in 问题[:15]:
        print("  ⚠ " + q)
    if len(问题) > 15:
        print("  ……还有 %d 处，先把上面这些处理了再看。" % (len(问题) - 15))
    print("（改完 Excel 后按 8 可以再查一遍）")
    print()


def 画树命令():
    import subprocess
    import webbrowser
    画树脚本 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "画树.py")
    树页面 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "家谱树.html")
    print("正在根据 Excel 表格重新画树……")
    结果 = subprocess.run([sys.executable, 画树脚本, 数据文件], capture_output=True,
                          text=True, encoding="utf-8")
    print(结果.stdout.strip())
    if 结果.returncode == 0:
        webbrowser.open("file:///" + 树页面.replace("\\", "/"))
        print("已在浏览器中打开。")
    else:
        print("画树失败：", 结果.stderr)


# ---------- 第四步：主循环，等着用户输入指令 ----------

帮助文字 = """
可用命令（输入序号或命令名都行）：
  1. 查人    —— 查某个人的父母、配偶、子女
  2. 祖先    —— 往上追某人的直系祖先
  3. 后代    —— 往下列出某人的所有后代（树状）
  4. 第几代  —— 列出某一代的所有人
  5. 全家    —— 一览全家人
  6. 帮助    —— 显示这份说明
  7. 画树    —— 根据表格重新画家谱树，并用浏览器打开
  8. 体检    —— 检查表格里编号、父母、配偶有没有填错
  0. 退出    —— 结束程序
"""

print("=" * 40)
print("  家谱查询程序")
print("=" * 40)
print(帮助文字)
打印体检(自动=True)

try:
    while True:
        指令 = input("请输入命令（0-8）> ").strip()
        if 指令 in ("退出", "q", "exit", "0"):
            print("再见！")
            break
        elif 指令 in ("查人", "1"):
            查个人()
        elif 指令 in ("祖先", "2"):
            查祖先()
        elif 指令 in ("后代", "3"):
            查后代()
        elif 指令 in ("第几代", "4"):
            按代列出()
        elif 指令 in ("全家", "5"):
            列出全家()
        elif 指令 in ("帮助", "h", "?", "6"):
            print(帮助文字)
        elif 指令 in ("画树", "7"):
            画树命令()
        elif 指令 in ("体检", "8"):
            打印体检()
        elif 指令 == "":
            continue
        else:
            print("看不懂这个命令，输入 6 可以看可用命令。")
except (EOFError, KeyboardInterrupt):
    # 窗口被关掉，或者按了 Ctrl+C / Ctrl+Z，安安静静地退出，不甩一堆英文报错
    print("\n再见！")
