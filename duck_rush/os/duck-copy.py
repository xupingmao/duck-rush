#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Duck Copy Tool
跨平台剪贴板复制工具, 支持 Windows / macOS / Linux(Wayland 与 X11)

Usage:
    cat file.txt | duck-copy.py          # 从管道复制
    duck-copy.py "要复制的文本"            # 复制参数中的文本
    duck-copy.py -f file.txt             # 复制文件内容

Examples:
    echo "hello" | duck-copy.py
    duck-copy.py "hello world"
"""

import sys
import argparse
import subprocess
import platform


def _try_run(cmd: list, text: str) -> bool:
    """尝试执行一个命令并把 text 通过 stdin 写入, 成功返回 True"""
    try:
        subprocess.run(cmd, input=text, text=True, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _copy_mac(text: str) -> None:
    subprocess.run(["pbcopy"], input=text, text=True, check=True)


def _copy_windows(text: str) -> None:
    # clip 是 Windows 自带的剪贴板命令, 从标准输入读取
    subprocess.run(["clip"], input=text, text=True, check=True)


def _copy_linux(text: str) -> None:
    # 依次尝试 Wayland / xclip / xsel
    if _try_run(["wl-copy"], text):
        return
    if _try_run(["xclip", "-selection", "clipboard"], text):
        return
    if _try_run(["xsel", "--clipboard", "--input"], text):
        return
    raise RuntimeError("未找到可用的剪贴板工具, 请安装 wl-clipboard / xclip / xsel")


def copy_text(text: str) -> None:
    """把文本写入系统剪贴板(跨平台)"""
    system = platform.system()
    if system == "Windows":
        _copy_windows(text)
    elif system == "Darwin":
        _copy_mac(text)
    elif system == "Linux":
        _copy_linux(text)
    else:
        raise RuntimeError("不支持的操作系统: %s" % system)


def read_source(args: argparse.Namespace) -> str:
    if args.file:
        with open(args.file, encoding=args.encoding) as fp:
            return fp.read()
    if args.text is not None:
        return args.text
    return sys.stdin.read()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="跨平台剪贴板复制工具, 支持 Windows / macOS / Linux")
    parser.add_argument("text", type=str, nargs="?", default=None,
                        help="要复制的文本(缺省则从标准输入读取)")
    parser.add_argument("-f", "--file", type=str, default=None,
                        help="复制指定文件的内容")
    parser.add_argument("--encoding", type=str, default="utf-8")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="复制成功后打印字符数")
    args = parser.parse_args()

    try:
        text = read_source(args)
        copy_text(text)
        if args.verbose:
            print("已复制 %d 个字符到剪贴板" % len(text), file=sys.stderr)
    except Exception as e:
        print("复制失败: %s" % e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
