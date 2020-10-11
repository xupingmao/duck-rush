#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/10/08 12:39:41
# @modified 2020/10/11 13:40:34

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("fpath")
args = parser.parse_args()

with open(args.fpath, "rb") as fp:
    bin = fp.read()

new_bin = bin.replace(b'\r', b'')
new_bin = bin.replace(b'\n', b'\r\n')

with open(args.fpath, "wb+") as fp:
    fp.write(new_bin)
