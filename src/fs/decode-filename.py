#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/08/08 18:12:48
# @modified 2021/08/08 18:48:22
# @filename decode-filename.py

import os
from urllib.parse import unquote


def main():
    command_list = []
    for fname in os.listdir("."):
        unquote_fname = unquote(fname)
        if unquote_fname != fname:
            print("旧文件名: {old_name}\n新文件名: {new_name}\n".format(old_name = fname, new_name = unquote_fname))
            command_list.append((fname, unquote_fname))

    if len(command_list) == 0:
        print("没有需要解码的文件名")
        return

    confirm_result = input("是否确认?(y/n):")
    if confirm_result == "y":
        for old_name, new_name in command_list:
            os.rename(old_name, new_name)
        print("重命名完成")

if __name__ == '__main__':
    main()