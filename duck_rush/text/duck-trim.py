# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/07/14
# @filename duck-trim.py
# @description 类似于 python 的 strip 函数, 去除每行两端的空白或指定字符

import sys
import argparse


def split_newline(line: str) -> "tuple[str, str]":
    """把一行拆分为 (内容, 行尾换行符), 支持 LF 与 CRLF"""
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def do_trim(fp, chars: str = None, left: bool = False,
            right: bool = False) -> None:
    """
    逐行读取并按 str.strip/lstrip/rstrip 的语义去除两端字符, 输出到 stdout。

    参数:
        fp:     输入文件对象或 stdin
        chars:  需要去除的字符集合, 为 None 时去除空白字符(同 str.strip())
        left:   只去除左侧(同 lstrip)
        right:  只去除右侧(同 rstrip)
    """
    for line in fp:
        content, nl = split_newline(line)
        if chars is None:
            if left and not right:
                content = content.lstrip()
            elif right and not left:
                content = content.rstrip()
            else:
                content = content.strip()
        else:
            if left and not right:
                content = content.lstrip(chars)
            elif right and not left:
                content = content.rstrip(chars)
            else:
                content = content.strip(chars)
        sys.stdout.write(content + nl)


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="去除每行两端的空白或指定字符(类似 python 的 strip 函数)")
    parser.add_argument("input", type=str, nargs="?", default="",
                        help="输入文件, 缺省为读取标准输入")
    parser.add_argument("-c", "--chars", type=str, default=None,
                        help="需要去除的字符集合, 缺省为空白字符")
    parser.add_argument("-l", "--left", action="store_true",
                        help="只去除左侧字符(类似 lstrip)")
    parser.add_argument("-r", "--right", action="store_true",
                        help="只去除右侧字符(类似 rstrip)")
    args: argparse.Namespace = parser.parse_args()

    if args.input == "":
        do_trim(sys.stdin, args.chars, args.left, args.right)
    else:
        with open(args.input, encoding="utf-8") as fp:
            do_trim(fp, args.chars, args.left, args.right)


if __name__ == '__main__':
    main()
