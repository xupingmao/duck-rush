'''
Author: xupingmao
email: 578749341@qq.com
Date: 2023-12-22 21:59:17
LastEditors: xupingmao
LastEditTime: 2023-12-22 22:10:51
FilePath: \duck-rush\duck_rush\utils\os_util.py
Description: 描述
'''
# encoding=utf-8

import subprocess

def popen(cmd):
    proc = subprocess.Popen(cmd,
                            shell=True,
                            stdout=subprocess.PIPE)
    return proc.stdout

def popen_str(cmd, encoding="utf-8") -> str:
    return popen(cmd).read().decode(encoding=encoding)
