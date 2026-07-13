#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Duck Paste Tool
跨平台剪贴板粘贴工具, 支持 Windows / macOS / Linux(Wayland 与 X11)

Usage:
    duck-paste.py                 # 输出剪贴板内容到标准输出
    duck-paste.py > file.txt      # 把剪贴板内容保存到文件

Examples:
    duck-paste.py
    duck-paste.py | grep "key"
"""

import sys
import argparse
import subprocess
import platform


def _try_capture(cmd: list) -> "str | None":
    """执行命令并捕获 stdout, 失败(命令不存在或异常)返回 None"""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return proc.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def _paste_mac() -> str:
    return subprocess.run(["pbpaste"], capture_output=True,
                          text=True, check=True).stdout


def _paste_windows() -> str:
    # PowerShell 自带 Get-Clipboard
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
        capture_output=True, text=True, check=True).stdout
    # Get-Clipboard 输出会额外带一个末尾换行, 去掉以保留原样
    if out.endswith("\r\n"):
        return out[:-2]
    if out.endswith("\n"):
        return out[:-1]
    return out


def _paste_linux() -> str:
    # 依次尝试 Wayland / xclip / xsel
    result = _try_capture(["wl-paste", "--no-newline"])
    if result is not None:
        return result
    result = _try_capture(["xclip", "-selection", "clipboard", "-o"])
    if result is not None:
        return result
    result = _try_capture(["xsel", "--clipboard", "--output"])
    if result is not None:
        return result
    raise RuntimeError("未找到可用的剪贴板工具, 请安装 wl-clipboard / xclip / xsel")


def paste_text() -> str:
    """读取系统剪贴板内容(跨平台)"""
    system = platform.system()
    if system == "Windows":
        return _paste_windows()
    if system == "Darwin":
        return _paste_mac()
    if system == "Linux":
        return _paste_linux()
    raise RuntimeError("不支持的操作系统: %s" % system)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="跨平台剪贴板粘贴工具, 支持 Windows / macOS / Linux")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="在 stderr 打印剪贴板字符数")
    args = parser.parse_args()

    try:
        text = paste_text()
        if args.verbose:
            print("剪贴板共 %d 个字符" % len(text), file=sys.stderr)
        # 使用 write 保留原始内容(含换行), 不额外追加换行
        sys.stdout.write(text)
    except Exception as e:
        print("粘贴失败: %s" % e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
