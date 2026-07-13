# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Description: 类似于 uniq 命令, 过滤或统计相邻重复的行
'''

import sys
import argparse

def build_key(line: str, skip_fields: int, skip_chars: int,
              check_chars: int, ignore_case: bool) -> str:
    '''根据参数计算出用于比较相邻行是否相同的 key'''
    # 先去掉行尾换行, 后续输出时再补回
    text = line.rstrip('\n').rstrip('\r')

    # 跳过前面的若干个字段(以空白字符分隔)
    if skip_fields > 0:
        tokens = text.split()
        if len(tokens) > skip_fields:
            text = ' '.join(tokens[skip_fields:])
        else:
            text = ''

    # 跳过前面的若干个字符
    if skip_chars > 0:
        text = text[skip_chars:]

    # 只比较前面若干个字符
    if check_chars > 0:
        text = text[:check_chars]

    if ignore_case:
        text = text.lower()

    return text


def do_uniq(fp, skip_fields: int = 0, skip_chars: int = 0,
            check_chars: int = 0, ignore_case: bool = False,
            count: bool = False, repeated: bool = False,
            unique: bool = False):
    '''读取文件并做 uniq 处理, 结果输出到 stdout'''
    prev_key = None
    prev_line = None
    group_count = 0

    def flush():
        nonlocal group_count, prev_line
        if group_count == 0:
            return
        is_repeated = group_count > 1
        # -d 只输出重复行, -u 只输出非重复行
        if repeated and unique:
            # 一行不可能既是重复又是唯一, 二者同时指定时不输出
            pass
        elif repeated and not is_repeated:
            return
        elif unique and is_repeated:
            return

        if count:
            print("%7d %s" % (group_count, prev_line), end="")
        else:
            print(prev_line, end="")

    for line in fp:
        key = build_key(line, skip_fields, skip_chars, check_chars, ignore_case)
        if prev_key is None:
            # 第一行
            prev_key = key
            prev_line = line
            group_count = 1
            continue

        if key == prev_key:
            group_count += 1
        else:
            flush()
            prev_key = key
            prev_line = line
            group_count = 1

    flush()


def main():
    parser = argparse.ArgumentParser(description="过滤或统计相邻重复的行(类似 uniq)")
    parser.add_argument("input", type=str, nargs="?", default="",
                        help="输入文件, 缺省为读取标准输入")
    parser.add_argument("-c", "--count", action="store_true",
                        help="在每行前面加上出现的次数")
    parser.add_argument("-d", "--repeated", action="store_true",
                        help="只显示重复出现的行(每组显示一次)")
    parser.add_argument("-u", "--unique", action="store_true",
                        help="只显示只出现一次的行")
    parser.add_argument("-i", "--ignore-case", action="store_true",
                        help="比较时忽略大小写")
    parser.add_argument("-f", "--skip-fields", type=int, default=0,
                        help="比较时跳过前面 N 个字段")
    parser.add_argument("-s", "--skip-chars", type=int, default=0,
                        help="比较时跳过前面 N 个字符")
    parser.add_argument("-w", "--check-chars", type=int, default=0,
                        help="比较时只检查前面 N 个字符")
    args = parser.parse_args()

    if args.input == "":
        do_uniq(sys.stdin, skip_fields=args.skip_fields,
                skip_chars=args.skip_chars, check_chars=args.check_chars,
                ignore_case=args.ignore_case, count=args.count,
                repeated=args.repeated, unique=args.unique)
    else:
        with open(args.input, encoding="utf-8") as fp:
            do_uniq(fp, skip_fields=args.skip_fields,
                    skip_chars=args.skip_chars, check_chars=args.check_chars,
                    ignore_case=args.ignore_case, count=args.count,
                    repeated=args.repeated, unique=args.unique)


if __name__ == '__main__':
    main()
