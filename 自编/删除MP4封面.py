import os
import subprocess
import tkinter as tk
from tkinter import filedialog


def remove_mp4_cover(video_file_path):
    """
    使用 ffmpeg 删除 .MP4 视频文件的封面。
    """
    try:
        # 构建临时文件路径，用于保存处理后的视频
        temp_file_path = video_file_path.replace(".mp4", "_no_cover.mp4")

        # ffmpeg 命令：拷贝视频和音频流，不包括封面
        command = [
            "ffmpeg",
            "-i", video_file_path,  # 输入文件
            "-map", "0",  # 保留所有流
            "-map", "-0:v:1",  # 删除封面流（第二个视频流）
            "-c", "copy",  # 拷贝视频和音频流
            temp_file_path  # 输出文件
        ]

        # 执行 ffmpeg 命令
        subprocess.run(command, check=True)

        # 替换原始文件
        os.replace(temp_file_path, video_file_path)
        print(f"Removed cover from: {video_file_path}")

    except Exception as e:
        print(f"Error processing {video_file_path}: {e}")


def process_folder(folder_path):
    """
    遍历指定文件夹和子文件夹，删除所有 .MP4 文件的封面。
    """
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(".mp4"):  # 仅处理 .MP4 文件
                video_file_path = os.path.join(root, file)
                remove_mp4_cover(video_file_path)


def main():
    # 使用 tkinter 打开文件夹选择对话框
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    folder_path = filedialog.askdirectory(title="Select a folder to process")

    if not folder_path:
        print("No folder selected. Exiting...")
        return

    print(f"Processing folder: {folder_path}")
    process_folder(folder_path)
    print("Processing complete.")


if __name__ == "__main__":
    main()
