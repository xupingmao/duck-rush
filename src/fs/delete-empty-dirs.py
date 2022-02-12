#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/10/07 00:14:39
# @modified 2021/10/07 00:43:40
# @filename delete-empty-dirs.py

"""删除空目录

类似的查找空目录的shell脚本: find . -empty -type d
"""

import os

def is_empty_dir(dirname):
    return os.path.isdir(dirname) and len(os.listdir(dirname)) == 0

def delete_empty_dirs(dirname, confirmed = False, print_info = True):
    count = 0

    for root, dirs, files in os.walk(dirname):
        for fname in dirs:
            fpath = os.path.join(root, fname)
            if is_empty_dir(fpath):
                count += 1
                if print_info:
                    print("[%03d] %s" % (count, fpath))

                if confirmed:
                    os.removedirs(fpath)

    if confirmed:
        return

    if count == 0:
        print("没有空目录")
        return

    print("")
    print("发现%s个空目录" % count)
    x = input("是否删除?(Y/N):")
    if x.upper() == "Y":
        delete_empty_dirs(dirname, True, False)
        print("删除完成!")


if __name__ == '__main__':
    # TODO 支持指定目录
    delete_empty_dirs(".")

