# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/12/25 12:07:03
# @modified 2021/12/25 15:03:40
# @filename duck-grep.py

import sys
import io
import os
import re
import argparse


def ensure_utf8_output():
    """强制以 UTF-8 输出, 避免 Windows 控制台代码页导致的中文乱码"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def match_substring(pattern: str, line: str) -> bool:
    return pattern in line


def iter_lines(stream, encoding: str):
    """从二进制流逐行解码, 返回 (行号, 去尾部换行的内容)"""
    for line_no, raw in enumerate(stream, 1):
        yield line_no, raw.decode(encoding, errors="replace").rstrip("\n")


def format_prefix(label: str, line_no: int, show_label: bool, line_number: bool) -> str:
    parts = []
    if show_label:
        parts.append(label)
    if line_number:
        parts.append(f"{line_no:4d}")
    if parts:
        return " │ ".join(parts) + " │ "
    return ""


def print_matches(pattern, regex, line_no, text, label, show_label, line_number, only_matching):
    prefix = format_prefix(label, line_no, show_label, line_number)
    if only_matching:
        matches = [m.group(0) for m in re.finditer(pattern, text)] if regex else [pattern]
        for m in matches:
            print(prefix + m)
    else:
        print(prefix + text)


def grep_stream(pattern, regex, line_number, only_matching, after, before,
                encoding, stream, label, show_label):
    """对单个输入流(文件或 stdin)执行 grep"""
    match_func = re.search if regex else match_substring

    # 无上下文时流式输出
    if after == 0 and before == 0:
        for line_no, line in iter_lines(stream, encoding):
            if match_func(pattern, line):
                print_matches(pattern, regex, line_no, line, label,
                              show_label, line_number, only_matching)
        return

    # 需要上下文时, 先把所有行读入内存
    lines = list(iter_lines(stream, encoding))
    n = len(lines)
    matched = [bool(match_func(pattern, text)) for _, text in lines]

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
        print_matches(pattern, regex, line_no, text, label,
                      show_label, line_number, only_matching and matched[j])


def main():
    parser = argparse.ArgumentParser(description="用于windows环境模拟linux的grep命令")
    parser.add_argument("pattern", type=str, help="匹配模式(支持正则)")
    parser.add_argument("files", nargs="*", help="要搜索的文件(不指定则从 stdin 读取)")
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
    parser.add_argument("-H", "--with-filename", action="store_true",
                        help="总是打印文件名(类似 grep -H)")
    parser.add_argument("--no-filename", action="store_true",
                        help="不打印文件名(类似 grep -h)")
    args = parser.parse_args()

    ensure_utf8_output()

    if args.files:
        # 多个文件或 -H 时显示文件名; -h 强制不显示
        if args.no_filename:
            show_label = False
        else:
            show_label = args.with_filename or len(args.files) > 1
        for fpath in args.files:
            if not os.path.exists(fpath):
                sys.stderr.write("duck-grep: %s: No such file or directory\n" % fpath)
                continue
            try:
                with open(fpath, "rb") as fp:
                    grep_stream(args.pattern, True, args.line_number, args.only_matching,
                                args.after_context, args.before_context, args.encoding,
                                fp, fpath, show_label)
            except Exception as e:
                sys.stderr.write("duck-grep: %s: %s\n" % (fpath, e))
    else:
        grep_stream(args.pattern, True, args.line_number, args.only_matching,
                    args.after_context, args.before_context, args.encoding,
                    sys.stdin.buffer, "", False)


if __name__ == '__main__':
    main()
