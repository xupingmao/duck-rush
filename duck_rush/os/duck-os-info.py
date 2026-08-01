# -*- coding:utf-8 -*-
"""
@Author       : xupingmao
@email        : 578749341@qq.com
@Date         : 2023-02-05 14:03:53
@LastEditors  : xupingmao
@LastEditTime : 2026-08-01
@FilePath     : duck_rush/os/duck-os-info.py
@Description  : 显示操作系统信息; 默认输出详细(detail), 可用 --part 只输出某一部分
"""

import os
import sys
import platform
import argparse
from typing import Callable, Dict


def print_row(key: str, value: object, indent: int = 2) -> None:
    print(" " * indent + key.ljust(20) + str(value))


def print_separator(char: str = "-", length: int = 40) -> None:
    print(char * length)


def print_section(title: str) -> None:
    print()
    print("[ %s ]" % title)
    print_separator()


def print_system() -> None:
    uname = platform.uname()
    print_section("系统信息")
    print_row("OS:", platform.system())
    print_row("版本:", platform.version())
    print_row("发布:", platform.release())
    print_row("主机名:", uname.node)


def print_hardware() -> None:
    print_section("硬件信息")
    print_row("架构:", platform.machine())
    print_row("处理器:", platform.processor())
    arch = platform.architecture()
    print_row("系统位数:", arch[0])
    print_row("链接格式:", arch[1])


def print_python() -> None:
    print_section("Python 信息")
    print_row("实现:", platform.python_implementation())
    print_row("版本:", platform.python_version())
    print_row("编译器:", platform.python_compiler())
    print_row("构建:", platform.python_build()[0])


def print_platform() -> None:
    print_section("平台标识")
    print_row("os.name:", os.name)
    print_row("sys.platform:", sys.platform)


def print_detail() -> None:
    """输出全部详细内容(默认行为)。"""
    print_system()
    print_hardware()
    print_python()
    print_platform()


def print_os_name() -> None:
    """仅输出操作系统名称一行。"""
    print(platform.system())


def print_os_version() -> None:
    """仅输出操作系统版本一行。"""
    print(platform.version())


# 各可独立输出的部分
SECTIONS: Dict[str, Callable[[], None]] = {
    "system": print_system,
    "hardware": print_hardware,
    "python": print_python,
    "platform": print_platform,
}


def main() -> None:
    """显示操作系统信息: 默认详细输出, 可用参数只输出指定部分或字段。"""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="显示操作系统信息。默认输出详细(detail), "
                    "可用参数只输出指定部分或字段。")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--os-name", action="store_true",
                       help="仅输出操作系统名称(platform.system())")
    group.add_argument("--os-version", action="store_true",
                       help="仅输出操作系统版本(platform.version())")
    group.add_argument("--part", "-p",
                       choices=list(SECTIONS.keys()),
                       help="只输出指定部分: system/hardware/python/platform")
    args: argparse.Namespace = parser.parse_args()

    if args.os_name:
        print_os_name()
        return
    if args.os_version:
        print_os_version()
        return
    if args.part:
        SECTIONS[args.part]()
        return
    print_detail()


if __name__ == "__main__":
    main()
