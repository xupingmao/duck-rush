# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/09/10
# @filename duck-diff.py
# @description 对比两个文件或两个目录的差异（不依赖 git）
"""duck-diff —— 对比两个文件或两个目录的差异，输出 unified diff 格式。

用法:
  duck-diff [选项] <文件A> <文件B>
  duck-diff [选项] <目录A> <目录B>

选项:
  -u, --context N   上下文行数（默认 3）
  -i, --ignore-case 忽略大小写差异
  -w, --ignore-space 忽略空白差异（连续空白视为一个空格，并去掉行首尾空白）
  --brief           只报告是否有差异，不输出具体内容
  --color           用颜色高亮 +/- 行
  --encoding NAME   读取文件时使用的编码（默认 utf-8）
  -h, --help        显示本帮助

目录模式会递归对比两侧的同名文件，输出 "只在左侧/只在右侧/内容不同" 的清单，
并可按 --brief 之外的方式展开每个文件的具体差异。
"""

import sys
import os
import argparse
import difflib
from dataclasses import dataclass
from typing import List, Optional, Tuple

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"


@dataclass
class DiffOptions:
    """影响对比行为的选项集合"""

    context: int = 3
    ignore_case: bool = False
    ignore_space: bool = False
    brief: bool = False
    color: bool = False
    encoding: str = "utf-8"


def read_lines(fpath: str, encoding: str) -> List[str]:
    """读取文件并按行切分, 保留行尾换行符以便 difflib 处理"""
    with open(fpath, "r", encoding=encoding, errors="replace") as fp:
        return fp.readlines()


def normalize(line: str, options: DiffOptions) -> str:
    """按选项归一化一行文本"""
    if options.ignore_space:
        line = " ".join(line.split())
    if options.ignore_case:
        line = line.lower()
    return line


def normalize_all(lines: List[str], options: DiffOptions) -> List[str]:
    return [normalize(line, options) for line in lines]


def colorize(line: str, options: DiffOptions) -> str:
    """给 diff 行上色, 未开启颜色时原样返回"""
    if not options.color:
        return line
    if line.startswith("+++") or line.startswith("---"):
        return CYAN + line + RESET
    if line.startswith("@@"):
        return CYAN + line + RESET
    if line.startswith("+"):
        return GREEN + line + RESET
    if line.startswith("-"):
        return RED + line + RESET
    return line


def diff_files(path_a: str, path_b: str, options: DiffOptions) -> List[str]:
    """对比两个文件, 返回 diff 文本行（无差异时返回空列表）"""
    lines_a = normalize_all(read_lines(path_a, options.encoding), options)
    lines_b = normalize_all(read_lines(path_b, options.encoding), options)

    if options.brief:
        if lines_a == lines_b:
            return []
        return ["文件不同: %s %s" % (path_a, path_b)]

    diff_iter = difflib.unified_diff(
        lines_a, lines_b,
        fromfile=path_a, tofile=path_b,
        n=options.context)
    return [colorize(line.rstrip("\n"), options) for line in diff_iter]


def list_relative_files(root: str) -> List[str]:
    """列出目录下所有文件的相对路径（统一使用 / 分隔）"""
    result: List[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            result.append(rel)
    return sorted(result)


def diff_dirs(dir_a: str, dir_b: str, options: DiffOptions) -> List[str]:
    """递归对比两个目录下的同名文件"""
    files_a = set(list_relative_files(dir_a))
    files_b = set(list_relative_files(dir_b))
    output: List[str] = []

    for rel in sorted(files_a - files_b):
        output.append("只在 %s: %s" % (dir_a, rel))
    for rel in sorted(files_b - files_a):
        output.append("只在 %s: %s" % (dir_b, rel))

    for rel in sorted(files_a & files_b):
        path_a = os.path.join(dir_a, rel)
        path_b = os.path.join(dir_b, rel)
        lines = diff_files(path_a, path_b, options)
        if lines:
            output.extend(lines)

    return output


def compare(path_a: str, path_b: str, options: DiffOptions) -> Tuple[List[str], int]:
    """对比两个路径, 返回 (输出行, 退出码)"""
    if os.path.isdir(path_a) and os.path.isdir(path_b):
        return diff_dirs(path_a, path_b, options), 0
    if os.path.isdir(path_a) or os.path.isdir(path_b):
        return ["无法对比: 一个是目录而另一个是文件"], 2

    output = diff_files(path_a, path_b, options)
    # 有差异时以退出码 1 结束, 方便在脚本里做判断
    return output, (1 if output else 0)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="对比两个文件或两个目录的差异")
    parser.add_argument("a", help="文件A 或 目录A")
    parser.add_argument("b", help="文件B 或 目录B")
    parser.add_argument("-u", "--context", type=int, default=3,
                        help="上下文行数（默认 3）")
    parser.add_argument("-i", "--ignore-case", action="store_true",
                        help="忽略大小写差异")
    parser.add_argument("-w", "--ignore-space", action="store_true",
                        help="忽略空白差异")
    parser.add_argument("--brief", action="store_true",
                        help="只报告是否有差异")
    parser.add_argument("--color", action="store_true",
                        help="用颜色高亮差异行")
    parser.add_argument("--encoding", default="utf-8",
                        help="读取文件的编码（默认 utf-8）")
    args = parser.parse_args(argv)

    options = DiffOptions(
        context=args.context,
        ignore_case=args.ignore_case,
        ignore_space=args.ignore_space,
        brief=args.brief,
        color=args.color,
        encoding=args.encoding)

    if not os.path.exists(args.a) or not os.path.exists(args.b):
        print("路径不存在: %s 或 %s" % (args.a, args.b), file=sys.stderr)
        return 2

    output, code = compare(args.a, args.b, options)
    for line in output:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
