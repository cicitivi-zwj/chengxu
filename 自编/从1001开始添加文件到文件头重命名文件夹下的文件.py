import os
import tkinter as tk
from tkinter import filedialog

def batch_rename_files(start_num=1001, case_sensitive=False, digit_width=0, preview=False):
    """
    递归重命名文件夹及其子文件夹内的所有文件。
    处理顺序：按文件夹名称升序，每个文件夹内先处理文件（按文件名升序），再处理子文件夹。
    序号全局连续递增。

    参数:
        start_num (int): 起始序号，默认1001
        case_sensitive (bool): 文件名/文件夹名排序时是否区分大小写，默认False（不区分）
        digit_width (int): 序号位数，0表示不补零，例如4表示格式化为0001，默认0
        preview (bool): 预览模式，True则只显示重命名结果但不实际修改文件，默认False
    """
    # 创建隐藏的Tk根窗口
    root = tk.Tk()
    root.withdraw()

    # 弹出文件夹选择对话框
    folder_path = filedialog.askdirectory(title="选择要重命名的文件夹")
    if not folder_path:
        print("未选择文件夹，程序退出。")
        return

    folder_path = os.path.abspath(folder_path)
    print(f"目标文件夹: {folder_path}\n")

    # 定义格式化序号函数
    def format_num(num):
        if digit_width > 0:
            return str(num).zfill(digit_width)
        return str(num)

    # 定义排序键函数
    def sort_key(name):
        return name if case_sensitive else name.lower()

    # 递归处理文件夹
    def process_folder(current_path, current_num):
        try:
            # 获取当前文件夹下的所有条目
            entries = os.listdir(current_path)
        except PermissionError:
            print(f"警告: 无权限访问文件夹 {current_path}，跳过")
            return current_num
        except OSError as e:
            print(f"警告: 无法读取文件夹 {current_path} ({e})，跳过")
            return current_num

        # 分离文件和子文件夹
        files = []
        subdirs = []
        for entry in entries:
            full_entry = os.path.join(current_path, entry)
            if os.path.isfile(full_entry):
                files.append(entry)
            elif os.path.isdir(full_entry):
                subdirs.append(entry)

        # 1. 处理当前文件夹下的文件（按名称排序）
        files.sort(key=sort_key)
        for old_name in files:
            old_path = os.path.join(current_path, old_name)
            name, ext = os.path.splitext(old_name)
            new_name = f"{format_num(current_num)}_{name}{ext}"
            new_path = os.path.join(current_path, new_name)

            if preview:
                print(f"[预览] {old_path} -> {new_path}")
            else:
                try:
                    os.rename(old_path, new_path)
                    print(f"成功: {old_path} -> {new_name}")
                except PermissionError:
                    print(f"失败: {old_path} (权限不足)")
                except OSError as e:
                    print(f"失败: {old_path} ({e})")
                except Exception as e:
                    print(f"失败: {old_path} (未知错误: {e})")
            current_num += 1

        # 2. 处理子文件夹（按名称排序，递归进入）
        subdirs.sort(key=sort_key)
        for subdir in subdirs:
            subdir_path = os.path.join(current_path, subdir)
            current_num = process_folder(subdir_path, current_num)

        return current_num

    # 执行重命名（从根文件夹开始）
    final_num = process_folder(folder_path, start_num)
    if not preview:
        print(f"\n全部处理完成。下一个可用序号: {final_num}")
    else:
        print("\n预览模式结束，未实际修改任何文件。")

if __name__ == "__main__":
    # ========= 使用示例 =========
    # 基本用法（起始1001，不区分大小写排序）
    batch_rename_files()

    # 其他用法示例（取消注释以测试不同配置）：
    # 1. 序号4位补零，起始500，区分大小写
    # batch_rename_files(start_num=500, case_sensitive=True, digit_width=4)

    # 2. 预览模式（仅显示不实际修改）
    # batch_rename_files(preview=True)