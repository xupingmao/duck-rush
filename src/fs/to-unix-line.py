#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/10/08 12:39:41
# @modified 2020/10/11 02:25:27

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("fpath")
args = parser.parse_args()

with open(args.fpath, "rb") as fp:
    bin = fp.read()

new_bin = bin.replace(b'\r', b'')

with open(args.fpath, "wb+") as fp:
    fp.write(new_bin)
