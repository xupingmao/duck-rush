# -*- coding:utf-8 -*-
"""
@Author       : xupingmao
@email        : 578749341@qq.com
@Date         : 2023-03-11 12:59:33
@LastEditors  : xupingmao
@LastEditTime : 2023-03-11 13:01:53
@FilePath     : /xiunobbsd:/projects/99-myprojects/duck_rush/src/code-tools/create-start-cmd.py
@Description  : 描述
"""
# encoding=utf-8
import os

CODE = """start cmd
"""

def main():
    """创建start-cmd.bat文件"""
    if not os.path.exists("./start-cmd.bat"):
        with open("./start-cmd.bat", "w+") as fp:
            fp.write(CODE)

if __name__ == "__main__":
    main()
