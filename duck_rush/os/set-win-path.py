# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2024-07-06 22:00:37
LastEditors: xupingmao
LastEditTime: 2024-07-06 22:27:37
FilePath: /duck_rush/duck_rush/os/set-win-path.py
Description: 描述
'''
# encoding=utf-8

import os
import sys
import fire

def add_path(value=""):
    path = os.environ["path"]
    if value in path:
        print(f"{value} already in PATH")
        return
    os.system("SystemPropertiesAdvanced.exe")

def remove_path(value=""):
    path = os.environ["path"]
    if value not in path:
        print(f"{value} not in path")
        return
    os.system("SystemPropertiesAdvanced.exe")

def main(op="add", value=""):
    """修改windows的PATH参数"""
    os.system("SystemPropertiesAdvanced.exe")
    return

    if value == "":
        print("path为空")
        sys.exit(1)
        return

    if op == "add":
        add_path(value)
    elif op == "remove":
        remove_path(value)
    else:
        print(f"invalid op: {op}")
        sys.exit(1)
    
    # os.system(f"SETX PATH %PATH%;{value} /m")

if __name__ == "__main__":
    fire.Fire(main)
