# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/07/14
# @filename duck-len.py
# @description 统计文本在 trim 之后每行的长度(类似 python 的 len(strip()))

import sys
import argparse


def split_newline(line: str) -> "tuple[str, str]":
    """把一行拆分为 (内容, 行尾换行符), 支持 LF 与 CRLF"""
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def trim_content(content: str, chars: str = None, left: bool = False,
                 right: bool = False) -> str:
    """按 str.strip/lstrip/rstrip 的语义去除两端字符"""
    if chars is None:
        if left and not right:
            return content.lstrip()
        if right and not left:
            return content.rstrip()
        return content.strip()
    if left and not right:
        return content.lstrip(chars)
    if right and not left:
        return content.rstrip(chars)
    return content.strip(chars)


def do_len(lines, chars: str = None, left: bool = False, right: bool = False,
           total: bool = False) -> None:
    """
    逐行统计, 在对每行做 trim 之后输出其长度, 结果写到 stdout。

    参数:
        lines:  可迭代的行序列(文件对象/stdin 或字符串列表)
        chars:  需要去除的字符集合, 为 None 时去除空白字符
        left:   只去除左侧字符
        right:  只去除右侧字符
        total:  额外在末尾输出所有行长度的总和
    """
    sum_len: int = 0
    for line in lines:
        content, _ = split_newline(line)
        trimmed: str = trim_content(content, chars, left, right)
        line_len: int = len(trimmed)
        sum_len += line_len
        print(line_len)

    if total:
        print("total: %d" % sum_len)


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="统计文本在 trim 之后每行的长度")
    parser.add_argument("text", type=str, nargs="?", default=None,
                        help="直接传入待统计的文本(可含换行); 缺省时读取标准输入")
    parser.add_argument("-f", "--file", type=str, default="",
                        help="输入文件, 指定后优先从文件读取(否则用 text 或 stdin)")
    parser.add_argument("-c", "--chars", type=str, default=None,
                        help="需要去除的字符集合, 缺省为空白字符")
    parser.add_argument("-l", "--left", action="store_true",
                        help="只去除左侧字符(类似 lstrip)")
    parser.add_argument("-r", "--right", action="store_true",
                        help="只去除右侧字符(类似 rstrip)")
    parser.add_argument("-t", "--total", action="store_true",
                        help="在末尾额外输出所有行长度的总和")
    args: argparse.Namespace = parser.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as fp:
            do_len(fp, args.chars, args.left, args.right, args.total)
    elif args.text is not None:
        do_len(args.text.splitlines(), args.chars, args.left,
               args.right, args.total)
    else:
        do_len(sys.stdin, args.chars, args.left, args.right, args.total)


if __name__ == '__main__':
    main()
