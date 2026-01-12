#!/usr/bin/env python3
"""
Duck Web Tools Launcher
跨平台命令行工具，用于启动 HTTP 服务器并打开 web-tools-index.html 文件
支持 Windows、Linux 和 MacOS 三大系统

Usage:
    duck-web-tools.py        # 启动 HTTP 服务器并打开 Web 工具索引页面
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
import time
import threading

def get_web_tools_dir():
    """
    获取 web-tools 目录的绝对路径
    """
    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return script_dir

def start_http_server(port=8000):
    """
    在 web-tools 目录下启动 HTTP 服务器
    """
    web_tools_dir = get_web_tools_dir()
    
    try:
        # 启动 HTTP 服务器
        server_process = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port)],
            cwd=web_tools_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待服务器启动
        time.sleep(1)
        
        # 检查服务器是否成功启动
        if server_process.poll() is not None:
            # 服务器启动失败
            stderr = server_process.stderr.read().decode('utf-8')
            print(f"错误: HTTP 服务器启动失败 - {stderr}", file=sys.stderr)
            return None
        
        print(f"HTTP 服务器已启动，端口: {port}")
        print(f"服务器目录: {web_tools_dir}")
        print(f"访问地址: http://localhost:{port}/web-tools-index.html")
        
        return server_process
    except Exception as e:
        print(f"错误: 启动 HTTP 服务器失败 - {e}", file=sys.stderr)
        return None

def open_browser(url):
    """
    跨平台打开浏览器
    """
    try:
        system = platform.system()
        
        if system == "Windows":
            # Windows 系统使用 start 命令
            subprocess.run(["start", "", url], shell=True, check=True)
        elif system == "Darwin":
            # MacOS 系统使用 open 命令
            subprocess.run(["open", url], check=True)
        elif system == "Linux":
            # Linux 系统使用 xdg-open 命令
            subprocess.run(["xdg-open", url], check=True)
        else:
            print(f"错误: 不支持的操作系统 {system}", file=sys.stderr)
            return False
        
        print(f"成功打开浏览器: {url}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"错误: 打开浏览器失败 - {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return False

def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(
        description='跨平台命令行工具，用于启动 HTTP 服务器并打开 Web 工具索引页面',
        epilog='示例:\n  duck-web-tools.py  # 启动 HTTP 服务器并打开 Web 工具索引页面'
    )
    
    # 添加可选参数
    parser.add_argument('--version', action='version', version='duck-web-tools 1.0')
    parser.add_argument('--verbose', '-v', action='store_true', help='启用详细输出模式')
    parser.add_argument('--port', '-p', type=int, default=8000, help='HTTP 服务器端口 (默认: 8000)')
    
    args = parser.parse_args()
    
    # 启动 HTTP 服务器
    server_process = start_http_server(args.port)
    
    if not server_process:
        return 1
    
    # 构建访问 URL
    url = f"http://localhost:{args.port}/web-tools-index.html"
    
    # 打开浏览器
    success = open_browser(url)
    
    if success:
        print("\n提示: 服务器将在您关闭终端时停止")
        print("如果需要手动停止服务器，请按 Ctrl+C")
        
        # 保持脚本运行，直到用户中断
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n正在停止 HTTP 服务器...")
            server_process.terminate()
            server_process.wait()
            print("HTTP 服务器已停止")
    else:
        # 打开浏览器失败，停止服务器
        server_process.terminate()
        server_process.wait()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
