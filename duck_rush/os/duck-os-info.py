# -*- coding:utf-8 -*-
"""
@Author       : xupingmao
@email        : 578749341@qq.com
@Date         : 2023-02-05 14:03:53
@LastEditors  : xupingmao
@LastEditTime : 2026-08-01
@FilePath     : duck_rush/os/duck-os-info.py
@Description  : 显示操作系统信息; 默认以表格格式输出详细(detail), 可用 --part 只输出某一部分, --json 输出 JSON 结构
"""

import os
import sys
import json
import platform
import unicodedata
import argparse
from typing import Callable, Dict, List, Tuple


def display_width(text: str) -> int:
    """计算字符串的显示宽度(CJK 等宽字符按 2 计数)。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def pad(text: str, width: int) -> str:
    """在右侧补空格使显示宽度等于 width。"""
    return text + " " * max(0, width - display_width(text))


def render_table(title: str, rows: List[Tuple[str, str]]) -> None:
    """渲染一个带边框的表格(项目 | 值 两列)。"""
    if title:
        print(title)
    if not rows:
        return
    key_w = max([display_width(k) for k, _ in rows] + [display_width("项目")])
    val_w = max([display_width(v) for _, v in rows] + [display_width("值")])
    sep = "+" + "-" * (key_w + 2) + "+" + "-" * (val_w + 2) + "+"
    print(sep)
    print("| " + pad("项目", key_w) + " | " + pad("值", val_w) + " |")
    print(sep)
    for key, value in rows:
        print("| " + pad(key, key_w) + " | " + pad(value, val_w) + " |")
    print(sep)


# 每行数据为 (json_key, 显示标签, 值); 表格使用显示标签(中文), --json 使用 json_key(英文)
Row = Tuple[str, str, str]


def get_system_rows() -> List[Row]:
    uname = platform.uname()
    return [
        ("os", "OS", platform.system()),
        ("version", "版本", platform.version()),
        ("release", "发布", platform.release()),
        ("node", "主机名", uname.node),
    ]


def get_hardware_rows() -> List[Row]:
    arch = platform.architecture()
    return [
        ("machine", "架构", platform.machine()),
        ("processor", "处理器", platform.processor()),
        ("bitness", "系统位数", arch[0]),
        ("linkage", "链接格式", arch[1]),
    ]


def get_python_rows() -> List[Row]:
    return [
        ("implementation", "实现", platform.python_implementation()),
        ("version", "版本", platform.python_version()),
        ("compiler", "编译器", platform.python_compiler()),
        ("build", "构建", platform.python_build()[0]),
    ]


def get_platform_rows() -> List[Row]:
    return [
        ("os_name", "os.name", os.name),
        ("sys_platform", "sys.platform", sys.platform),
    ]


# 各可独立输出的部分: 名称 -> (标题, 取数据行的[json_key, 标签, 值]的函数)
SECTIONS: Dict[str, Tuple[str, Callable[[], List[Row]]]] = {
    "system": ("系统信息", get_system_rows),
    "hardware": ("硬件信息", get_hardware_rows),
    "python": ("Python 信息", get_python_rows),
    "platform": ("平台标识", get_platform_rows),
}


def rows_to_table(rows: List[Row]) -> List[Tuple[str, str]]:
    """把 (json_key, 标签, 值) 转为表格需要的 (标签, 值)。"""
    return [(label, value) for _, label, value in rows]


def rows_to_dict(rows: List[Row]) -> Dict[str, str]:
    """把 (json_key, 标签, 值) 转为 --json 使用的 {json_key: 值}。"""
    return {key: value for key, _, value in rows}


def build_info_dict() -> Dict[str, Dict[str, str]]:
    """把所有部分的数据组织成嵌套字典(英文 key), 供 --json 输出。"""
    result: Dict[str, Dict[str, str]] = {}
    for name, (_, func) in SECTIONS.items():
        result[name] = rows_to_dict(func())
    return result


def print_detail() -> None:
    """按表格格式输出全部内容(默认行为)。"""
    for name in SECTIONS:
        title, func = SECTIONS[name]
        print()
        render_table(title, rows_to_table(func()))


def print_section_table(name: str) -> None:
    """按表格格式输出指定部分。"""
    title, func = SECTIONS[name]
    print()
    render_table(title, rows_to_table(func()))


def print_os_name() -> None:
    """仅输出操作系统名称一行。"""
    print(platform.system())


def print_os_version() -> None:
    """仅输出操作系统版本一行。"""
    print(platform.version())


def main() -> None:
    """显示操作系统信息: 默认以表格格式详细输出, 可用参数只输出指定部分或字段, --json 输出 JSON 结构。"""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="显示操作系统信息。默认以表格格式详细输出, "
                    "可用参数只输出指定部分或字段, --json 输出 JSON 结构。")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--os-name", action="store_true",
                       help="仅输出操作系统名称(platform.system())")
    group.add_argument("--os-version", action="store_true",
                       help="仅输出操作系统版本(platform.version())")
    group.add_argument("--part", "-p",
                       choices=list(SECTIONS.keys()),
                       help="只输出指定部分: system/hardware/python/platform")
    parser.add_argument("--json", "-j", action="store_true",
                        help="以 JSON 结构输出(可与 --part 配合只输出该部分)")
    args: argparse.Namespace = parser.parse_args()

    if args.json:
        if args.os_name:
            print(json.dumps(platform.system(), ensure_ascii=False))
        elif args.os_version:
            print(json.dumps(platform.version(), ensure_ascii=False))
        elif args.part:
            _, func = SECTIONS[args.part]
            print(json.dumps(rows_to_dict(func()), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(build_info_dict(), ensure_ascii=False, indent=2))
        return

    if args.os_name:
        print_os_name()
        return
    if args.os_version:
        print_os_version()
        return
    if args.part:
        print_section_table(args.part)
        return
    print_detail()


if __name__ == "__main__":
    main()
