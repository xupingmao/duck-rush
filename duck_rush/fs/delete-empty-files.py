#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/10/07 00:14:39
# @modified 2021/10/07 00:43:40
# @filename delete-empty-dirs.py

import fire
import os

def is_empty_file(fpath):
    try:
        st = os.stat(fpath)
        return st.st_size == 0
    except:
        return False

def delete_empty_dirs(dirname=".", confirmed = False, print_info = True):
    """删除目录下的空文件"""
    count = 0

    for root, dirs, files in os.walk(dirname):
        for fname in files:
            fpath = os.path.join(root, fname)
            if is_empty_file(fpath):
                count += 1
                if print_info:
                    print("[%03d] %s" % (count, fpath))

                if confirmed:
                    os.remove(fpath)

    if confirmed:
        return

    if count == 0:
        print("没有空目录")
        return

    print("")
    print("发现%s个空文件" % count)
    x = input("是否删除?(Y/N):")
    if x.upper() == "Y":
        delete_empty_dirs(dirname, True, False)
        print("删除完成!")


if __name__ == '__main__':
    # 支持指定目录
    fire.Fire(delete_empty_dirs)

