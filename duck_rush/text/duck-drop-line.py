# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/08/10
# @filename duck-drop-line.py
# @description 移除管道中的空白行或指定的行(按行号 / 正则), 支持多种条件组合

import sys
import io
import re
import argparse
from typing import List, Set, Optional, cast


def ensure_utf8_output() -> None:
    """强制以 UTF-8 输出, 避免 Windows 控制台代码页导致的中文乱码"""
    out = cast(io.TextIOWrapper, sys.stdout)
    try:
        out.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def split_newline(line: str) -> "tuple[str, str]":
    """把一行拆分为 (内容, 行尾换行符), 支持 LF 与 CRLF"""
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def parse_line_spec(spec: str) -> Set[int]:
    """解析行号规格, 支持逗号分隔与区间 ``N-M`` (1-based, 闭区间)。

    例如 ``"1,3,5-8"`` 表示第 1,3,5,6,7,8 行。非法区间(如 8-5)会被忽略。
    """
    result: Set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if part == "":
            continue
        if "-" in part:
            lo_s, hi_s = part.split("-", 1)
            lo_s, hi_s = lo_s.strip(), hi_s.strip()
            if lo_s == "" or hi_s == "":
                raise ValueError("行号区间缺少端点: %r" % part)
            lo, hi = int(lo_s), int(hi_s)
            if lo <= hi:
                result.update(range(lo, hi + 1))
        else:
            result.add(int(part))
    return result


def build_drop_set(line_specs: List[str]) -> Set[int]:
    """合并多个 --line 参数, 返回需要删除的(1-based)行号集合。"""
    drop: Set[int] = set()
    for spec in line_specs:
        drop |= parse_line_spec(spec)
    return drop


def should_drop(line_no: int, content: str,
                drop_lines: Set[int],
                blank: bool,
                patterns: List[re.Pattern]) -> bool:
    """按任一条件命中即判定删除(OR 语义)。"""
    if blank and content.strip() == "":
        return True
    if line_no in drop_lines:
        return True
    for pat in patterns:
        if pat.search(content):
            return True
    return False


def drop_lines(fp, out,
               blank: bool,
               drop_lines: Set[int],
               patterns: List[re.Pattern]) -> None:
    """逐行读取, 按条件过滤后写出, 保留原始换行符。"""
    for lineno, raw in enumerate(fp, start=1):
        content, nl = split_newline(raw)
        if should_drop(lineno, content, drop_lines, blank, patterns):
            continue
        out.write(content + nl)


def main() -> None:
    ensure_utf8_output()

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="移除管道中的空白行或指定的行(按行号 / 正则), 多条件为 OR 关系")
    parser.add_argument("input", type=str, nargs="?", default="",
                        help="输入文件, 缺省为读取标准输入")
    parser.add_argument("-b", "--blank", action="store_true",
                        help="删除空白行(含仅含空白字符的行)")
    parser.add_argument("-l", "--line", type=str, action="append", default=[],
                        metavar="SPEC",
                        help="删除指定的行号, 如 1,3,5-8 (可重复, 1-based, 闭区间)")
    parser.add_argument("-p", "--pattern", type=str, action="append", default=[],
                        metavar="REGEX",
                        help="删除匹配正则的行(可重复, 与 -i 配合忽略大小写)")
    parser.add_argument("-i", "--ignore-case", action="store_true",
                        help="正则匹配时忽略大小写")
    parser.add_argument("-E", "--encoding", default="utf-8",
                        help="输入内容的编码(默认 utf-8, GBK 文件可传 gbk)")
    args: argparse.Namespace = parser.parse_args()

    if not args.blank and not args.line and not args.pattern:
        parser.error("至少需要指定一种删除条件: -b/--blank, -l/--line 或 -p/--pattern")

    drop_lines_set = build_drop_set(args.line)

    flags = re.IGNORECASE if args.ignore_case else 0
    patterns = [re.compile(p, flags) for p in args.pattern]

    if args.input == "":
        data = sys.stdin.buffer.read()
        text = data.decode(args.encoding, errors="replace")
        drop_lines(io.StringIO(text), sys.stdout, args.blank, drop_lines_set, patterns)
    else:
        with open(args.input, encoding=args.encoding, errors="replace") as fp:
            drop_lines(fp, sys.stdout, args.blank, drop_lines_set, patterns)


if __name__ == '__main__':
    main()
