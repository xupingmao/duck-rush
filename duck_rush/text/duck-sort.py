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

def parse_number(num_str):
    try:
        return float(num_str)
    except ValueError:
        return 0


def do_sort(fp, reverse = False, numeric = False):
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
        if numeric:
            key = parse_number(first_token)
        else:
            key = line
            
        temp.append((key, line))

    temp.sort(key = lambda x:x[0], reverse = reverse)
    for size, line in temp:
        print(line, end="")


def main():
    parser = argparse.ArgumentParser(description = "duck_rush文本排序工具")
    parser.add_argument("-r", "--reverse", action = "store_true", help = "逆序排序")
    parser.add_argument("-n", "--numeric-sort", action = "store_true",
                        help = "按数字大小排序(类似 sort -n), 默认按文件大小单位排序")
    args = parser.parse_args()
    do_sort(sys.stdin, reverse = args.reverse, numeric = args.numeric_sort)

if __name__ == '__main__':
    main()
