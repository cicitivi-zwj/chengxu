import os
import tkinter as tk
from tkinter import simpledialog, messagebox

def remove_between_chars(filename, start_char, end_char):
    """移除文件名中两个指定字符之间的字符串（包含这两个字符）"""
    start_index = filename.find(start_char)
    end_index = filename.find(end_char, start_index + 1)
    if start_index != -1 and end_index != -1:
        return filename[:start_index] + filename[end_index + 1:]
    return filename

def rename_files_in_directory(directory, start_char, end_char):
    for root, dirs, files in os.walk(directory):
        for filename in files:
            new_filename = remove_between_chars(filename, start_char, end_char)
            old_file_path = os.path.join(root, filename)
            new_file_path = os.path.join(root, new_filename)

            # 如果新的文件名已经存在，则覆盖它
            if new_filename != filename:
                try:
                    os.replace(old_file_path, new_file_path)
                    print(f"Renamed: {old_file_path} -> {new_file_path}")
                except Exception as e:
                    print(f"Error renaming {old_file_path} to {new_file_path}: {e}")

def main():
    # 创建主窗口
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口

    # 提示用户输入文件夹路径
    directory = simpledialog.askstring("Input", "Enter the directory path:")
    if not directory:
        messagebox.showerror("Error", "Directory path cannot be empty.")
        return

    # 提示用户输入要删除的开始和结束字符
    start_char = simpledialog.askstring("Input", "Enter the starting character:")
    if not start_char or len(start_char) != 1:
        messagebox.showerror("Error", "Starting character must be a single character.")
        return

    end_char = simpledialog.askstring("Input", "Enter the ending character:")
    if not end_char or len(end_char) != 1:
        messagebox.showerror("Error", "Ending character must be a single character.")
        return

    # 确认操作
    if messagebox.askyesno("Confirmation", f"Are you sure you want to remove the string between '{start_char}' and '{end_char}' (inclusive) from filenames in '{directory}'?"):
        # 重命名文件
        try:
            rename_files_in_directory(directory, start_char, end_char)
            messagebox.showinfo("Success", "Files have been renamed successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

if __name__ == "__main__":
    main()
