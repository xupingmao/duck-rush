# -*- coding: utf-8 -*-
# @author xupingmao
# @since 2026/08/01
# @filename duck-colors.py
# @description 展示终端 16 色 ANSI 配色示例(8 标准色 + 8 高亮色)

import argparse
import sys
from typing import List, Tuple

# (颜色名称, 前景 SGR 码, 背景 SGR 码)
COLORS: List[Tuple[str, int, int]] = [
    ("black", 30, 40),
    ("red", 31, 41),
    ("green", 32, 42),
    ("yellow", 33, 43),
    ("blue", 34, 44),
    ("magenta", 35, 45),
    ("cyan", 36, 46),
    ("white", 37, 47),
    ("light_grey", 90, 100),
    ("light_red", 91, 101),
    ("light_green", 92, 102),
    ("light_yellow", 93, 103),
    ("light_blue", 94, 104),
    ("light_magenta", 95, 105),
    ("light_cyan", 96, 106),
    ("light_white", 97, 107),
]

RESET = "\033[0m"


def _swatch(name: str, fg: int, bg: int, sample: str) -> str:
    """返回一行: 彩色背景色块 + 该色前景显示的名称 + 码值说明。"""
    block = f"{RESET}\033[{bg}m{sample}{RESET}"
    name_colored = f"{RESET}\033[{fg}m{name}{RESET}"
    return f"  {block}  {name_colored}  (fg={fg} bg={bg})"


def show_colors(sample: str) -> None:
    print("ANSI 16 色示例 (8 标准色 + 8 高亮色)\n")

    print("标准色 (Normal):")
    for name, fg, bg in COLORS[:8]:
        print(_swatch(name, fg, bg, sample))

    print("\n高亮色 (Bright):")
    for name, fg, bg in COLORS[8:]:
        print(_swatch(name, fg, bg, sample))

    print()


def list_names() -> None:
    print("可用颜色名称:")
    for name, fg, bg in COLORS:
        print(f"  {name}  (fg={fg} bg={bg})")
    print()


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="展示终端 16 色 ANSI 配色示例(8 标准色 + 8 高亮色)。")
    parser.add_argument("--sample", type=str, default="  duck  ",
                        help="色块中显示的示例文本 (缺省 '  duck  ')")
    parser.add_argument("--list", action="store_true",
                        help="仅列出 16 个颜色名称, 不显示色块")
    args: argparse.Namespace = parser.parse_args()

    # 管道/重定向到文件时, 不输出转义码, 仅列出名称, 保证可读性
    if args.list or not sys.stdout.isatty():
        list_names()
        return

    show_colors(args.sample)


if __name__ == "__main__":
    main()
