# -*- coding:utf-8 -*-
"""
@Author       : xupingmao
@email        : 578749341@qq.com
@Date         : 2022-07-02 17:20:56
@LastEditors  : xupingmao
@LastEditTime : 2022-07-02 17:21:03
@FilePath     : /xnoted:/projects/duck_rush/src/code-template/python/hello.py
@Description  : 描述
"""

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("Usage: python hello.py  # 打印 hello,world!")
        sys.exit(0)
    print("hello,world!")
