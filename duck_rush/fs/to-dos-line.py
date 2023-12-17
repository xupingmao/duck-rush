#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/10/08 12:39:41
# @modified 2020/10/11 13:40:34

import fire
import sys
import termcolor

def red_color(text):
    return termcolor.colored(text, "red")

def main(fpath = ""):
    """把文件转换成dos风格的换行(\r\n)"""

    if fpath == "":
        print(red_color("ERR: fpath不能为空"))
        sys.exit(1)

    with open(fpath, "rb") as fp:
        bin = fp.read()

    new_bin = bin.replace(b'\r', b'')
    new_bin = bin.replace(b'\n', b'\r\n')

    with open(fpath, "wb+") as fp:
        fp.write(new_bin)

if __name__ == "__main__":
    fire.Fire(main)
