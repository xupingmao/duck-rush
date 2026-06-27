# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/12/25 12:07:03
# @modified 2026/06/27 15:03:40
# @filename duck-replace.py

"""
文本替换工具 — 从管道读取数据，将匹配的字符串替换为目标字符串。

用法:
    echo "hello world" | duck-replace.py "world" "there"        # glob 匹配
    echo "hello 123"  | duck-replace.py --regex "\d+" "NUMBER"  # 正则匹配

支持两种匹配模式:
    1. glob 匹配（默认），将 glob 通配符转为非贪婪正则
    2. 正则匹配，直接使用 re.sub
"""

import sys
import re
import argparse


def glob_to_regex(pattern: str) -> str:
    """
    将 glob 通配符模式转换为用于子串匹配的正则表达式。

    转换规则:
        *  → .*?  （非贪婪，匹配最短的可能）
        ?  → .
        .  → \.   （转义）
        其余特殊字符相应转义
    """
    parts: list[str] = []
    i: int = 0
    n: int = len(pattern)
    while i < n:
        c: str = pattern[i]
        if c == '*':
            # * 匹配任意多个字符（贪婪，更符合直觉）
            parts.append('.*')
        elif c == '?':
            # ? 匹配任意单个字符
            parts.append('.')
        elif c in '.^$+{}[]()|\\':
            # 其余正则特殊字符转义
            parts.append('\\' + c)
        else:
            parts.append(c)
        i += 1
    return ''.join(parts)


def do_replace(pattern: str, replacement: str, regex: bool = False,
               ignore_case: bool = False) -> None:
    """
    从 stdin 逐行读取，将匹配 pattern 的子串替换为 replacement，输出到 stdout。

    参数:
        pattern:     匹配模式（glob 或 正则）
        replacement: 替换字符串
        regex:       是否使用正则匹配（否则用 glob）
        ignore_case: 是否忽略大小写
    """
    flags: int = re.IGNORECASE if ignore_case else 0

    if regex:
        # 直接使用用户提供的正则表达式
        regex_pattern: str = pattern
    else:
        # 将 glob 模式转换为用于子串匹配的正则
        regex_pattern = glob_to_regex(pattern)

    compiled: re.Pattern = re.compile(regex_pattern, flags)

    for line in sys.stdin:
        # 替换行内所有匹配的子串
        result: str = compiled.sub(replacement, line)
        sys.stdout.write(result)


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="文本替换工具 — 从管道读取数据，替换匹配的字符串")
    parser.add_argument("pattern", type=str,
                        help="匹配模式（glob 或 正则，默认 glob）")
    parser.add_argument("replacement", type=str,
                        help="替换字符串")
    parser.add_argument("-r", "--regex", action="store_true",
                        help="使用正则匹配模式（默认 glob）")
    parser.add_argument("-i", "--ignore-case", action="store_true",
                        help="忽略大小写")
    args: argparse.Namespace = parser.parse_args()

    do_replace(args.pattern, args.replacement, args.regex, args.ignore_case)


if __name__ == '__main__':
    main()
