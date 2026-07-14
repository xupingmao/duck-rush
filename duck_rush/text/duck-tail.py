# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2024-09-02 00:06:21
LastEditors: xupingmao
LastEditTime: 2024-09-02 00:16:04
FilePath: /duck_rush/duck_rush/text/duck-tail.py
Description: 复刻 GNU tail 命令, 打印文件/标准输入的末尾部分
    用法: duck-tail [选项] [文件]...
    选项:
        -n, --lines=NUM   打印末尾 NUM 行(默认 10); -NUM=除最后NUM行; +NUM=从第NUM行起
        -c, --bytes=NUM   打印末尾 NUM 字节(符号语义同上)
        -f, --follow      文件增长时持续输出新增内容
        -q, --quiet       不打印文件头(==> 文件名 <==)
        -v, --verbose     总是打印文件头
        -NUM              等同 --lines=NUM; +NUM 等同 --lines=+NUM
    无文件时读取标准输入; 单独使用 '-' 也表示标准输入
'''

import sys
import os
import re
import time
import argparse


def parse_count(val: str, command: str):
    '''解析带符号的行数/字节数, 返回 (kind, num)。语义对齐 GNU:
    head: +K/无符号 -> 开头K个(first); -K -> 除最后K个(butlast)
    tail: -K/无符号 -> 末尾K个(last, 自动截断); +K -> 从第K个起(from)'''
    val = val.strip()
    sign = ''
    if val.startswith('+'):
        sign, num = '+', int(val[1:])
    elif val.startswith('-'):
        sign, num = '-', int(val[1:])
    else:
        num = int(val)
    if command == 'head':
        return ('butlast', num) if sign == '-' else ('first', num)
    else:  # tail
        return ('from', num) if sign == '+' else ('last', num)


def slice_lines(data: bytes, kind: str, num: int) -> bytes:
    lines = data.splitlines(keepends=True)
    if kind == 'first':
        return b''.join(lines[:num])
    if kind == 'last':
        return b''.join(lines[-num:]) if num > 0 else b''
    if kind == 'from':
        return b''.join(lines[num - 1:]) if num >= 1 else data
    if kind == 'butlast':
        return b''.join(lines[:-num]) if num > 0 else data
    return data


def slice_bytes(data: bytes, kind: str, num: int) -> bytes:
    if kind == 'first':
        return data[:num]
    if kind == 'last':
        return data[-num:] if num > 0 else b''
    if kind == 'from':
        return data[num - 1:] if num >= 1 else data
    if kind == 'butlast':
        return data[:-num] if num > 0 else data
    return data


def preprocess(argv, allow_plus):
    '''把 -N / +N 简写转换为 --lines=N / --lines=+N
    当 -N / +N 紧跟在 -n/-c 等需要参数的选项之后时, 它是该选项的值, 不转换'''
    out = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('-n', '--lines', '-c', '--bytes'):
            if i + 1 < len(argv) and re.fullmatch(r'[+-]?\d+', argv[i + 1] or ''):
                val = argv[i + 1]
                opt = '--lines=' if a in ('-n', '--lines') else '--bytes='
                out.append(opt + val)
                i += 2
                continue
            out.append(a)
        elif re.fullmatch(r'-\d+', a):
            out.append("--lines=" + a[1:])
        elif allow_plus and re.fullmatch(r'\+\d+', a):
            out.append("--lines=+" + a[1:])
        else:
            out.append(a)
        i += 1
    return out


def process_file(path, mode, kind, num, header):
    if header:
        sys.stdout.buffer.write(("==> %s <==\n" % path).encode("utf-8"))
    if path == '-' or path == '':
        data = sys.stdin.buffer.read()
    else:
        with open(path, 'rb') as f:
            data = f.read()
    if mode == 'bytes':
        sys.stdout.buffer.write(slice_bytes(data, kind, num))
    else:
        sys.stdout.buffer.write(slice_lines(data, kind, num))


def follow_file(path):
    '''从文件末尾开始持续输出新增内容'''
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            while True:
                chunk = f.read()
                if chunk:
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                else:
                    # 文件被截断则回到开头
                    try:
                        if os.path.getsize(path) < f.tell():
                            f.seek(0)
                    except OSError:
                        pass
                    time.sleep(1.0)
    except KeyboardInterrupt:
        pass


def main():
    argv = preprocess(sys.argv[1:], allow_plus=True)
    parser = argparse.ArgumentParser(
        prog="duck-tail", description="打印末尾部分, 复刻 GNU tail")
    parser.add_argument("files", nargs="*", default=[])
    parser.add_argument("-n", "--lines", default=None)
    parser.add_argument("-c", "--bytes", default=None)
    parser.add_argument("-f", "--follow", action="store_true")
    parser.add_argument("-q", "--quiet", "--silent", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.lines is not None and args.bytes is not None:
        sys.stderr.write("duck-tail: 不能同时使用 -n 和 -c\n")
        sys.exit(1)

    if args.bytes is not None:
        mode = 'bytes'
        kind, num = parse_count(args.bytes, 'tail')
    else:
        n = args.lines if args.lines is not None else '10'
        mode = 'lines'
        kind, num = parse_count(str(n), 'tail')

    files = args.files if args.files else ['-']

    if args.quiet:
        need_header = False
    elif args.verbose:
        need_header = True
    else:
        need_header = len(files) > 1

    for i, path in enumerate(files):
        if i > 0 and need_header:
            sys.stdout.buffer.write(b"\n")
        process_file(path, mode, kind, num, header=need_header)

    # -f 仅对单个真实文件生效(标准输入不支持跟随)
    if args.follow and len(files) == 1 and files[0] not in ('-', ''):
        follow_file(files[0])


if __name__ == "__main__":
    main()
