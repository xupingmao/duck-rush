# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2021/08/08 18:12:48
LastEditors: xupingmao
LastEditTime: 2024-06-29 12:15:15
FilePath: /duck_rush/duck_rush/fs/decode-filename.py
Description: 描述
'''

import os
import fire

from urllib.parse import unquote


def decode_filename_in_dir(dirname="."):
    command_list = []
    for fname in os.listdir(dirname):
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
        print("重命名完成!")

if __name__ == '__main__':
    fire.Fire(decode_filename_in_dir)