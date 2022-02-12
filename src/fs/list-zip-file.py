#!/usr/bin/env python3
# @author xupingmao
# @since 2021/10/07 00:39:06
# @modified 2021/10/07 00:52:35
# @filename list-zip-file.py
import sys
import os


def list_zip_file(fpath):
    os.system("7z l %r" % fpath)

def print_help():
    exe_file = os.path.basename(sys.argv[0])
    print("查看压缩文件包的内容，使用方式如下:")
    print("")
    print("$> %s 文件名" % exe_file)
    print("")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print_help()
    else:
        list_zip_file(sys.argv[1])
