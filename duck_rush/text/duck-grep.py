# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/12/25 12:07:03
# @modified 2021/12/25 15:03:40
# @filename duck-sort.py

import os
import sys
import re
import fire

def do_grep(search_key = ""):
    """用于windows环境模拟linux的grep命令"""
    fp = sys.stdin
    while True:
        line = fp.readline()
        if line == "":
            # 读取到文件结尾
            break
        clean_line = line.strip()
        if clean_line == "":
            continue
        if search_key in clean_line:
            print(clean_line)


def main():
    fire.Fire(do_grep)

if __name__ == '__main__':
    main()
