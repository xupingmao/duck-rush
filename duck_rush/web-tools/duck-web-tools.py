#!/usr/bin/env python3
"""
Duck Web Tools Launcher
跨平台命令行工具，用于打开 web-tools-index.html 文件
支持 Windows、Linux 和 MacOS 三大系统

Usage:
    duck-web-tools.py        # 打开 web-tools-index.html 文件
    duck-web-tools.py --help  # 显示帮助信息
    duck-web-tools.py --version  # 显示版本信息

Examples:
    # 在 Windows 上
    duck-web-tools.py

    # 在 Linux 上
    ./duck-web-tools.py

    # 在 MacOS 上
    ./duck-web-tools.py
"""

import os
import platform
import subprocess
import sys
import argparse

def get_index_file_path():
    """
    获取 web-tools-index.html 文件的绝对路径
    """
    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 构建 index 文件路径
    index_path = os.path.join(script_dir, 'web-tools-index.html')
    return index_path

def open_browser(path):
    """
    跨平台打开浏览器
    """
    try:
        system = platform.system()
        
        if system == "Windows":
            # Windows 系统使用 start 命令
            subprocess.run(["start", "", path], shell=True, check=True)
        elif system == "Darwin":
            # MacOS 系统使用 open 命令
            subprocess.run(["open", path], check=True)
        elif system == "Linux":
            # Linux 系统使用 xdg-open 命令
            subprocess.run(["xdg-open", path], check=True)
        else:
            print(f"错误: 不支持的操作系统 {system}", file=sys.stderr)
            return False
        
        print(f"成功打开 Web 工具索引: {path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"错误: 打开失败 - {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return False

def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(
        description='跨平台命令行工具，用于打开 web-tools-index.html 文件',
        epilog='示例:\n  duck-web-tools.py  # 打开 Web 工具索引页面'
    )
    
    # 添加可选参数
    parser.add_argument('--version', action='version', version='duck-web-tools 1.0')
    parser.add_argument('--verbose', '-v', action='store_true', help='启用详细输出模式')
    
    args = parser.parse_args()
    
    # 获取 index 文件路径
    index_path = get_index_file_path()
    
    # 检查文件是否存在
    if not os.path.exists(index_path):
        print(f"错误: 文件不存在 - {index_path}", file=sys.stderr)
        return 1
    
    # 打开浏览器
    success = open_browser(index_path)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
