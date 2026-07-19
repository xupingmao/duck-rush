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

import sys
import argparse
import random
import hashlib

def parse_number(num_str):
    try:
        return float(num_str)
    except ValueError:
        return 0


def do_sort(fp, reverse = False, numeric = False, random_sort = False):
    # 随机排序时每次运行生成新的随机盐, 使相同行哈希一致(保持相邻)、整体顺序随机
    salt = str(random.getrandbits(128)).encode("utf-8")

    temp = []
    while True:
        line = fp.readline()
        if line == "":
            # 读取到文件结尾
            break
        clean_line = line.strip()
        if clean_line == "":
            continue
        first_token = clean_line.split()[0]
        if random_sort:
            key = hashlib.md5(salt + line.encode("utf-8", "replace")).digest()
        elif numeric:
            key = parse_number(first_token)
        else:
            key = line

        temp.append((key, line))

    # 随机排序忽略 reverse, 按哈希值升序(相同行因哈希一致而保持相邻)
    temp.sort(key = lambda x:x[0], reverse = (reverse and not random_sort))
    for size, line in temp:
        print(line, end="")


def main():
    parser = argparse.ArgumentParser(description = "duck_rush文本排序工具")
    parser.add_argument("-r", "--reverse", action = "store_true", help = "逆序排序")
    parser.add_argument("-n", "--numeric-sort", action = "store_true",
                        help = "按数字大小排序(类似 sort -n), 默认按文件大小单位排序")
    parser.add_argument("-R", "--random-sort", action = "store_true",
                        help = "随机排序(类似 sort -R), 每次运行结果不同, 相同行保持相邻")
    args = parser.parse_args()
    do_sort(sys.stdin, reverse = args.reverse, numeric = args.numeric_sort,
            random_sort = args.random_sort)

if __name__ == '__main__':
    main()
