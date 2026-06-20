# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/12/25 12:07:03
# @modified 2021/12/25 15:03:40
# @filename duck-grep.py

import sys
import re
import argparse


def match_substring(pattern: str, line: str) -> bool:
    return pattern in line


def do_grep(pattern: str = "", line_number: bool = False, regex: bool = False):
    """用于windows环境模拟linux的grep命令"""
    match_func = re.search if regex else match_substring
    for line_no, line in enumerate(sys.stdin, 1):
        line = line.rstrip("\n")
        if match_func(pattern, line):
            if line_number:
                print(f"{line_no:4d} │ {line}")
            else:
                print(line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pattern", type=str, default="")
    parser.add_argument("-n", "--line-number", action="store_true",
                        help="show line numbers")
    parser.add_argument("-E", "--regexp", action="store_true",
                        help="pattern is a regular expression")
    args = parser.parse_args()
    do_grep(args.pattern, args.line_number, args.regexp)


if __name__ == '__main__':
    main()
