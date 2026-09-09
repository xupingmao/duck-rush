# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/09/10
# @filename duck-du.py
# @description 统计目录/文件的磁盘占用，找出占空间的大目录
"""duck-du —— 统计目录或文件的磁盘占用（类似 du 命令）。

用法:
  duck-du [选项] [路径...]

选项:
  -d, --max-depth N  只统计到指定层级（默认不限）
  -a, --all          同时列出文件（默认只列目录）
  -t, --top N        只显示占用最大的 N 项
  --human            大小以人类可读方式显示（K/M/G/T）
  --min-size SIZE    只显示大于该大小的条目，如 100M、1G（默认不过滤）
  -h, --help         显示本帮助

示例:
  duck-du -d 1 --human ~/Downloads   查看 Downloads 下各子目录的占用
  duck-du -a -t 20 --human .         找出当前目录下最大的 20 个文件/目录
"""

import sys
import os
import re
import argparse
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

SIZE_UNITS = ["B", "K", "M", "G", "T"]
SIZE_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*([bkmgtBKMGT]?)$")


@dataclass
class DuOptions:
    """统计行为的选项集合"""

    max_depth: Optional[int] = None
    show_all: bool = False
    top: Optional[int] = None
    human: bool = False
    min_size: int = 0


def parse_size(text: str) -> int:
    """解析 100M / 1G / 512 这类大小描述, 返回字节数"""
    matched = SIZE_PATTERN.match(text.strip())
    if matched is None:
        raise ValueError("无法解析大小: %s" % text)
    value = float(matched.group(1))
    unit = matched.group(2).upper()
    if not unit:
        unit = "B"
    return int(value * (1024 ** SIZE_UNITS.index(unit)))


def format_size(size: int, human: bool) -> str:
    """按是否可读格式化字节数"""
    if not human:
        return str(size)
    value = float(size)
    unit_index = 0
    while value >= 1024 and unit_index < len(SIZE_UNITS) - 1:
        value /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return "%d%s" % (int(value), SIZE_UNITS[unit_index])
    return "%.1f%s" % (value, SIZE_UNITS[unit_index])


def get_depth(root: str, path: str) -> int:
    """计算 path 相对 root 的层级深度, root 自身为 0"""
    root_key = os.path.normpath(root)
    path_key = os.path.normpath(path)
    if path_key == root_key:
        return 0
    rel = os.path.relpath(path_key, root_key)
    return rel.count(os.sep) + 1


def scan(root: str) -> Tuple[Dict[str, int], Dict[str, int]]:
    """遍历 root, 返回 (目录累计大小, 文件大小)。

    目录大小包含其所有后代文件的大小；路径统一用 normpath 规范化，
    保证与 root 的比较结果一致。
    """
    root_key = os.path.normpath(root)
    dir_sizes: Dict[str, int] = {}
    file_sizes: Dict[str, int] = {}

    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        current = os.path.normpath(dirpath)
        dir_sizes.setdefault(current, 0)

        for name in filenames:
            fpath = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(fpath)
            except OSError:
                continue
            file_sizes[os.path.normpath(fpath)] = size

            # 把文件大小累加到从当前目录到 root 的所有祖先目录
            node = current
            while True:
                dir_sizes[node] = dir_sizes.get(node, 0) + size
                if node == root_key:
                    break
                parent = os.path.normpath(os.path.dirname(node))
                if parent == node:
                    break
                node = parent

    return dir_sizes, file_sizes


def build_entries(root: str, options: DuOptions) -> List[Tuple[int, str]]:
    """按选项收集并排序 (大小, 路径) 列表"""
    dir_sizes, file_sizes = scan(root)

    entries: List[Tuple[int, str]] = []
    for path, size in dir_sizes.items():
        if options.max_depth is not None and get_depth(root, path) > options.max_depth:
            continue
        entries.append((size, path))

    if options.show_all:
        for path, size in file_sizes.items():
            if options.max_depth is not None:
                if get_depth(root, os.path.dirname(path)) + 1 > options.max_depth:
                    continue
            entries.append((size, path))

    entries = [item for item in entries if item[0] >= options.min_size]
    entries.sort(key=lambda item: (-item[0], item[1]))

    if options.top is not None:
        entries = entries[:options.top]

    return entries


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="统计目录/文件的磁盘占用")
    parser.add_argument("paths", nargs="*", default=["."], help="待统计的路径（默认当前目录）")
    parser.add_argument("-d", "--max-depth", type=int, default=None,
                        help="只统计到指定层级")
    parser.add_argument("-a", "--all", action="store_true",
                        help="同时列出文件")
    parser.add_argument("-t", "--top", type=int, default=None,
                        help="只显示占用最大的 N 项")
    parser.add_argument("--human", action="store_true",
                        help="大小以人类可读方式显示")
    parser.add_argument("--min-size", default=None,
                        help="只显示大于该大小的条目，如 100M、1G")
    args = parser.parse_args(argv)

    min_size = 0
    if args.min_size:
        try:
            min_size = parse_size(args.min_size)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2

    options = DuOptions(
        max_depth=args.max_depth,
        show_all=args.all,
        top=args.top,
        human=args.human,
        min_size=min_size)

    for path in args.paths:
        if not os.path.exists(path):
            print("路径不存在: %s" % path, file=sys.stderr)
            continue
        if os.path.isfile(path):
            size = os.path.getsize(path)
            print("%s\t%s" % (format_size(size, options.human), path))
            continue

        for size, entry in build_entries(path, options):
            print("%s\t%s" % (format_size(size, options.human), entry))

    return 0


if __name__ == "__main__":
    sys.exit(main())
