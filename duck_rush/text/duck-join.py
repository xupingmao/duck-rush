# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/12/25
# @filename duck-join.py
# @description 用连接符拼接每行输入, 功能类似 Python 的 str.join

import sys
import io
import argparse


def ensure_utf8_output():
    """强制以 UTF-8 输出, 避免 Windows 控制台代码页导致的中文乱码"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(
        description="用连接符拼接每行输入, 类似 Python 的 str.join")
    parser.add_argument("sep", default=",", nargs="?",
                        help="连接符(默认空字符串, 类似 ''.join)")
    parser.add_argument("-E", "--encoding", default="utf-8",
                        help="输入内容的编码(默认 utf-8, GBK 文件可传 gbk)")
    args = parser.parse_args()

    ensure_utf8_output()

    parts = []
    for raw in sys.stdin.buffer:
        line = raw.decode(args.encoding, errors="replace").rstrip("\r\n")
        parts.append(line)

    print(args.sep.join(parts))


if __name__ == '__main__':
    main()
