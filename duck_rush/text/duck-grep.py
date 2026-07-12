# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/12/25 12:07:03
# @modified 2021/12/25 15:03:40
# @filename duck-grep.py

import sys
import io
import re
import argparse


def ensure_utf8_streams(encoding: str):
    """统一编解码, 避免 Windows 控制台代码页(cp936等)导致的中文乱码

    - 输入: 从 sys.stdin.buffer 读取原始字节, 按指定编码解码
    - 输出: 强制以 UTF-8 写入, 适配 Git Bash / 现代终端
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def match_substring(pattern: str, line: str) -> bool:
    return pattern in line


def do_grep(pattern: str = "", line_number: bool = False, regex: bool = False,
            only_matching: bool = False, after: int = 0, before: int = 0,
            encoding: str = "utf-8"):
    """用于windows环境模拟linux的grep命令

    - only_matching: 类似 grep -o, 只输出匹配到的部分
    - after/before: 类似 grep -A/-B, 输出匹配行之后/之前的上下文
    - encoding: 输入内容的编码(默认 utf-8, GBK 文件可传 gbk)
    """
    match_func = re.search if regex else match_substring

    # 从 stdin.buffer 读取原始字节, 避免 Windows 默认代码页解码错误
    def read_lines():
        for line_no, raw in enumerate(sys.stdin.buffer, 1):
            yield line_no, raw.decode(encoding, errors="replace").rstrip("\n")

    # 无上下文时流式输出, 保持原有行为
    if after == 0 and before == 0:
        for line_no, line in read_lines():
            if not match_func(pattern, line):
                continue
            if only_matching:
                matches = [m.group(0) for m in re.finditer(pattern, line)] if regex else [pattern]
                for m in matches:
                    print_line(line_no, m, line_number)
            else:
                print_line(line_no, line, line_number)
        return

    # 需要上下文时, 先把所有行读入内存
    lines = list(read_lines())

    n = len(lines)
    matched = [bool(match_func(pattern, text)) for _, text in lines]

    # 计算需要打印的行范围(匹配行前后各 after/before 行)
    print_idx = [False] * n
    for i in range(n):
        if matched[i]:
            lo = max(0, i - before)
            hi = min(n - 1, i + after)
            for j in range(lo, hi + 1):
                print_idx[j] = True

    printed_any = False
    prev_printed = False
    for j in range(n):
        if not print_idx[j]:
            prev_printed = False
            continue
        # 不同匹配组之间用 -- 分隔(类似 grep)
        if printed_any and not prev_printed:
            print("--")
        printed_any = True
        prev_printed = True

        line_no, text = lines[j]
        if matched[j] and only_matching:
            matches = [m.group(0) for m in re.finditer(pattern, text)] if regex else [pattern]
            for m in matches:
                print_line(line_no, m, line_number)
        else:
            print_line(line_no, text, line_number)


def print_line(line_no: int, content: str, line_number: bool):
    if line_number:
        print(f"{line_no:4d} │ {content}")
    else:
        print(content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pattern", type=str, default="")
    parser.add_argument("-n", "--line-number", action="store_true",
                        help="show line numbers")
    parser.add_argument("-o", "--only-matching", action="store_true",
                        help="只打印匹配到的部分(类似 grep -o)")
    parser.add_argument("-A", "--after-context", type=int, default=0, metavar="NUM",
                        help="打印匹配行之后的 NUM 行上下文(类似 grep -A)")
    parser.add_argument("-B", "--before-context", type=int, default=0, metavar="NUM",
                        help="打印匹配行之前的 NUM 行上下文(类似 grep -B)")
    parser.add_argument("-E", "--encoding", default="utf-8",
                        help="输入内容的编码(默认 utf-8, GBK 文件可传 gbk)")
    args = parser.parse_args()
    ensure_utf8_streams(args.encoding)
    do_grep(args.pattern, args.line_number, True, args.only_matching,
            args.after_context, args.before_context, args.encoding)


if __name__ == '__main__':
    main()
