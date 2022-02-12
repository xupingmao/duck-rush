#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/10/08 12:39:41
# @modified 2021/12/25 20:05:23

import argparse
import os

MAX_FILE_SIZE = 1024**2
FIX_NAMES = set(["Makefile", "configure", "build.sh", "build_config.mk"])

def log_info(fmt, *args):
    print(fmt % args)

def get_file_size(fpath):
    stat = os.stat(fpath)
    return stat.st_size

def fix_file(fpath):
    with open(fpath, "rb") as fp:
        bin = fp.read()

    new_bin = bin.replace(b'\r', b'')

    with open(fpath, "wb+") as fp:
        fp.write(new_bin)

def read_file_bytes(fpath):
    with open(fpath, "rb") as fp:
        return fp.read()

def is_code_file(fname):
    return fname in FIX_NAMES

def check_dir(dirname):
    result = []
    for root, dirs, files in os.walk(dirname):
        for fname in files:
            if not is_code_file(fname):
                continue
            fpath = os.path.join(root, fname)
            if get_file_size(fpath) < MAX_FILE_SIZE:
                bytes = read_file_bytes(fpath)
                if b'\r' in bytes:
                    result.append(fpath)

    return result

def confirm_and_fix_files(files):
    if len(files) == 0:
        log_info("没有找到符合条件的文件")

    log_info("找到%d个文件", len(files))
    for fpath in files:
        log_info(fpath)

    x = input("是否修复(Y/N):")
    if x.lower() == "y":
        log_info("准备修复...")
        for fpath in files:
            fix_file(fpath)
    else:
        log_info("修复取消")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fpath")
    args = parser.parse_args()

    if os.path.isdir(args.fpath):
        files = check_dir(args.fpath)
        confirm_and_fix_files(files)
    else:
        fix_file(args.fpath)

if __name__ == '__main__':
    main()
