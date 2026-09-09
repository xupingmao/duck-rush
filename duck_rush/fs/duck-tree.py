# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/09/10
# @filename duck-tree.py
# @description 以树状结构展示目录内容
"""duck-tree —— 以树状结构展示目录内容（跨平台，类似 tree 命令）。

用法:
  duck-tree [选项] [路径]

选项:
  -L, --level N     最多展示的层级深度（默认不限）
  -a, --all         显示隐藏文件/目录（以 . 开头的条目）
  -d, --dirs-only   只显示目录
  -s, --size        显示文件大小（人类可读）
  --no-color        关闭颜色输出（默认: 目录用亮蓝色，可执行文件用亮绿色）
  -h, --help        显示本帮助

末尾会输出 "N directories, M files" 的统计信息。
"""

import sys
import os
import argparse
from dataclasses import dataclass
from typing import List, Optional, Tuple

BLUE = "\033[94m"
GREEN = "\033[92m"
RESET = "\033[0m"

SIZE_UNITS = ["B", "K", "M", "G", "T"]


@dataclass
class TreeOptions:
    """树状展示的选项集合"""

    max_level: Optional[int] = None
    show_all: bool = False
    dirs_only: bool = False
    show_size: bool = False
    color: bool = True


def format_size(size: int) -> str:
    """把字节数格式化成人类可读的形式"""
    value = float(size)
    unit_index = 0
    while value >= 1024 and unit_index < len(SIZE_UNITS) - 1:
        value /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return "%d%s" % (int(value), SIZE_UNITS[unit_index])
    return "%.1f%s" % (value, SIZE_UNITS[unit_index])


def list_children(dirpath: str, options: TreeOptions) -> Tuple[List[str], List[str]]:
    """列出目录下的 (子目录, 子文件), 均按名称排序, 目录排在前面"""
    dirs: List[str] = []
    files: List[str] = []
    try:
        names = os.listdir(dirpath)
    except OSError as e:
        print("无法读取目录: %s (%s)" % (dirpath, e), file=sys.stderr)
        return dirs, files

    for name in sorted(names):
        if not options.show_all and name.startswith("."):
            continue
        full = os.path.join(dirpath, name)
        if os.path.isdir(full):
            dirs.append(name)
        elif not options.dirs_only:
            files.append(name)

    return dirs, files


def decorate(name: str, full: str, is_dir: bool, options: TreeOptions) -> str:
    """按类型给条目加上颜色或后缀"""
    display = name
    if options.show_size and not is_dir:
        try:
            display = "%s (%s)" % (name, format_size(os.path.getsize(full)))
        except OSError:
            pass
    if not options.color:
        return display + ("/" if is_dir else "")
    if is_dir:
        return BLUE + display + "/" + RESET
    if os.access(full, os.X_OK):
        return GREEN + display + RESET
    return display


def walk(dirpath: str, prefix: str, level: int, options: TreeOptions,
         stat: "dict") -> None:
    """递归打印目录树"""
    if options.max_level is not None and level > options.max_level:
        return

    dirs, files = list_children(dirpath, options)
    entries: List[Tuple[str, bool]] = [(name, True) for name in dirs]
    entries.extend((name, False) for name in files)

    for index, (name, is_dir) in enumerate(entries):
        is_last = index == len(entries) - 1
        connector = "`-- " if is_last else "|-- "
        full = os.path.join(dirpath, name)
        print(prefix + connector + decorate(name, full, is_dir, options))

        if is_dir:
            stat["dirs"] += 1
            child_prefix = prefix + ("    " if is_last else "|   ")
            walk(full, child_prefix, level + 1, options, stat)
        else:
            stat["files"] += 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="以树状结构展示目录内容")
    parser.add_argument("path", nargs="?", default=".", help="目录路径（默认当前目录）")
    parser.add_argument("-L", "--level", type=int, default=None,
                        help="最多展示的层级深度")
    parser.add_argument("-a", "--all", action="store_true",
                        help="显示隐藏文件/目录")
    parser.add_argument("-d", "--dirs-only", action="store_true",
                        help="只显示目录")
    parser.add_argument("-s", "--size", action="store_true",
                        help="显示文件大小")
    parser.add_argument("--no-color", action="store_true", help="关闭颜色输出")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.path):
        print("不是目录: %s" % args.path, file=sys.stderr)
        return 2

    options = TreeOptions(
        max_level=args.level,
        show_all=args.all,
        dirs_only=args.dirs_only,
        show_size=args.size,
        color=not args.no_color)

    stat = {"dirs": 0, "files": 0}
    print(args.path)
    walk(args.path, "", 1, options, stat)
    print("")
    print("%d directories, %d files" % (stat["dirs"], stat["files"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
