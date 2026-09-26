import os
from tkinter import Tk, filedialog

def get_folder_path():
    # 创建一个Tkinter根窗口，但不显示
    root = Tk()
    root.withdraw()
    
    # 弹出文件夹选择对话框
    folder_path = filedialog.askdirectory(title="请选择文件夹")
    return folder_path

def generate_tree(directory, prefix=""):
    """
    生成树形目录结构
    :param directory: 当前目录路径
    :param prefix: 前缀，用于缩进和连接线
    :return: 树形目录字符串
    """
    tree = ""
    # 获取目录下的所有文件和文件夹
    items = os.listdir(directory)
    for i, item in enumerate(items):
        full_path = os.path.join(directory, item)
        # 判断是否是最后一个项目
        is_last = (i == len(items) - 1)
        # 添加当前项目
        tree += f"{prefix}{'└── ' if is_last else '├── '}{item}\n"
        if os.path.isdir(full_path):
            # 如果是文件夹，递归生成子目录
            extension = "    " if is_last else "│   "
            tree += generate_tree(full_path, prefix + extension)
    return tree

def save_tree_to_file(folder_path, tree):
    """
    将树形目录保存到文件
    :param folder_path: 文件夹路径
    :param tree: 树形目录字符串
    """
    output_file = os.path.join(folder_path, "SX.TXT")
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(tree)
    print(f"树形目录已保存到: {output_file}")

def main():
    # 获取用户选择的文件夹路径
    folder_path = get_folder_path()
    
    if folder_path:
        # 生成树形目录结构
        tree = generate_tree(folder_path)
        
        # 将树形目录保存到文件
        save_tree_to_file(folder_path, tree)
    else:
        print("未选择文件夹。")

if __name__ == "__main__":
    main()
