import os


def write_directory_structure(folder_path, output_file):
    """
    遍历指定文件夹及其子文件夹，将文件夹和文件名以树形结构输出到文本文件中。
    """
    try:
        with open(output_file, "w", encoding="utf-8") as file:
            for root, dirs, files in os.walk(folder_path):
                # 计算当前文件夹的深度，用于树形缩进
                level = root.replace(folder_path, "").count(os.sep)
                indent = "    " * level  # 每一层缩进4个空格
                folder_name = os.path.basename(root)

                # 写入文件夹名
                file.write(f"{indent}|-- {folder_name}\n")

                # 写入当前文件夹下的文件名
                sub_indent = "    " * (level + 1)
                for filename in files:
                    file.write(f"{sub_indent}|-- {filename}\n")

        print(f"Directory structure successfully written to {output_file}")

    except Exception as e:
        print(f"Error: {e}")


def main():
    # 获取用户输入的文件夹路径
    folder_path = input("Please enter the folder path: ").strip()

    # 检查文件夹路径是否存在
    if not os.path.isdir(folder_path):
        print("The specified folder path does not exist. Please try again.")
        return

    # 定义输出文件名
    output_file = "MULU.TXT"

    # 写入目录结构
    write_directory_structure(folder_path, output_file)


if __name__ == "__main__":
    main()
