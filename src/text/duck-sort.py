# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/12/25 12:07:03
# @modified 2021/12/25 15:03:40
# @filename duck-sort.py

import os
import sys
import re
import argparse

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
