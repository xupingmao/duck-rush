# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2023-12-23 12:09:14
LastEditors: xupingmao
LastEditTime: 2023-12-23 12:37:35
FilePath: /duck_rush/duck_rush/text/duck-sort.py
Description: 描述
'''

import os
import sys
import re
import argparse

duck_rush_dir = os.environ.get("DUCK_RUSH_DIR", "")
if duck_rush_dir not in sys.path:
    sys.path.append(duck_rush_dir)


from duck_rush.utils import os_util

def parse_size(size_str):
    result = re.match(r"([0-9\.]+)(B|K|M|G)", size_str)
    if result:
        g1 = result.group(1)
        g2 = result.group(2)
        # print(g1,g2)
        if g2 == "B":
            return float(g1)
        if g2 == "K":
            return float(g1) * 1024
        if g2 == "M":
            return float(g1) * 1024 ** 2
        if g2 == "G":
            return float(g1) * 1024 ** 3
        return -1
    else:
        return 0

def do_sort(fp, reverse = False):
    temp = []
    while True:
        line = fp.readline()
        if line == "":
            # 读取到文件结尾
            break
        clean_line = line.strip()
        if clean_line == "":
            continue
        fsize = clean_line.split()[0]
        size = parse_size(fsize)
        temp.append((size, line))

    temp.sort(key = lambda x:x[0], reverse = reverse)
    for size, line in temp:
        print(line, end="")


def main():
    parser = argparse.ArgumentParser(description = "duck_rush文本排序工具")
    parser.add_argument("-r", action = "store_true")
    args = parser.parse_args()
    do_sort(sys.stdin, reverse = args.r)

if __name__ == '__main__':
    main()
