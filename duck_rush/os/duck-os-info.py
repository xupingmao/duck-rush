# -*- coding:utf-8 -*-
"""
@Author       : xupingmao
@email        : 578749341@qq.com
@Date         : 2023-02-05 14:03:53
@LastEditors  : xupingmao
@LastEditTime : 2023-03-11 12:35:06
@FilePath     : /xiunobbsd:/projects/99-myprojects/duck_rush/src/os/detect-os.py
@Description  : 描述
"""

import os
import sys
import platform
import argparse

def print_row(key: str, value, indent: int = 2):
    print(" " * indent + key.ljust(20) + str(value))

def print_separator(char: str = "-", length: int = 40):
    print(char * length)

def print_section(title: str):
    print()
    print("[ %s ]" % title)
    print_separator()

def print_detail():
    uname = platform.uname()

    print_section("系统信息")
    print_row("OS:", platform.system())
    print_row("版本:", platform.version())
    print_row("发布:", platform.release())
    print_row("主机名:", uname.node)

    print_section("硬件信息")
    print_row("架构:", platform.machine())
    print_row("处理器:", platform.processor())
    arch = platform.architecture()
    print_row("系统位数:", arch[0])
    print_row("链接格式:", arch[1])

    print_section("Python 信息")
    print_row("实现:", platform.python_implementation())
    print_row("版本:", platform.python_version())
    print_row("编译器:", platform.python_compiler())
    print_row("构建:", platform.python_build()[0])

    print_section("平台标识")
    print_row("os.name:", os.name)
    print_row("sys.platform:", sys.platform)

def print_simple():
    print(platform.system())

def main(detail=False):
    """检测操作系统类型"""
    if detail:
        print_detail()
    else:
        print_simple()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--detail", action="store_true")
    args = parser.parse_args()
    main(args.detail)