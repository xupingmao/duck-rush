#!/usr/bin/env python3
"""
Duck Open Tool
跨平台文件/程序打开工具，支持 Windows、Linux 和 MacOS 三大系统

Usage:
    duck-open.py <target>        # 打开指定文件、目录或URL

Examples:
    duck-open.py "C:/Users/User/Desktop/file.txt"
    duck-open.py "/home/user/Documents"
    duck-open.py "https://www.baidu.com"
"""

import os
import platform
import subprocess
import sys
import argparse

def open_file(path):
    """
    跨平台打开文件/目录/URL
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
        
        print(f"成功打开: {path}")
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
        description='跨平台文件/程序打开工具，支持 Windows、Linux 和 MacOS 三大系统',
        epilog='示例:\n  duck-open.py "C:/Users/User/Desktop/file.txt"\n  duck-open.py "/home/user/Documents"\n  duck-open.py "https://www.baidu.com"'
    )
    
    # 添加位置参数
    parser.add_argument('target', help='要打开的文件、目录或URL')
    
    # 添加可选参数（用于后续扩展）
    parser.add_argument('--version', action='version', version='duck-open 1.0')
    parser.add_argument('-v', '--verbose', action='store_true', help='启用详细输出模式')
    
    args = parser.parse_args()
    
    path = args.target
    success = open_file(path)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
