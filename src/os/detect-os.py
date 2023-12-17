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
import fire

def print_row(key: str, value):
    print(key.rjust(20), value)

def print_detail():
    # 参考文档： https://blog.csdn.net/KnownAll/article/details/81560050
    # os.name 用于判断模块是否可用，只注册了三个值 posix/nt/java
    print_row("os.name:", os.name)
    # sys.platform 依赖在构建配置时指定的编译器定义
    print_row("sys.platform:", sys.platform)
    # platform.system() 会返回更详细的系统信息，比如 Linux/Windows/Darwin
    print_row("platform.system():", platform.system())
    print_row("platform.version():", platform.version())

def print_simple():
    print(platform.system())

def main(detail=False):
    """检测操作系统类型"""
    if detail:
        print_detail()
    else:
        print_simple()


if __name__ == "__main__":
    fire.Fire(main)