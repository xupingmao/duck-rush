# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/12/25
# @filename duck-split.py
# @description 按分隔符切分输入, 功能类似 Python 的 str.split, 每个片段单独一行输出

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
        description="按分隔符切分输入, 类似 Python 的 str.split")
    parser.add_argument("sep", default=None, nargs="?",
                        help="分隔符(默认按任意空白字符切分, 类似 str.split())")
    parser.add_argument("-E", "--encoding", default="utf-8",
                        help="输入内容的编码(默认 utf-8, GBK 文件可传 gbk)")
    args = parser.parse_args()

    ensure_utf8_output()

    data = sys.stdin.buffer.read().decode(args.encoding, errors="replace")
    # 去掉末尾换行, 避免产生多余的空片段
    data = data.rstrip("\r\n")

    if args.sep is None:
        # 类似 str.split(): 按任意空白字符切分并丢弃空串
        tokens = data.split()
    else:
        tokens = data.split(args.sep)

    for tok in tokens:
        print(tok)


if __name__ == '__main__':
    main()
