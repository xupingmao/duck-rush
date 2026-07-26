# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2023-03-11 13:14:36
LastEditors: xupingmao
LastEditTime: 2024-06-29 12:24:34
FilePath: /duck_rush/duck_rush/code/code-tools/c99-to-c89.py
Description: 描述
'''
# -*- coding:utf-8 -*-
"""
@Author       : xupingmao
@email        : 578749341@qq.com
@Date         : 2023-03-11 13:14:36
@LastEditors  : xupingmao
@LastEditTime : 2023-03-11 13:15:11
@FilePath     : duck_rush/src/code-tools/c99-to-c89.py
@Description  : 描述
"""
# encoding=utf-8

def main():
    """TODO 把C99程序转换成C89程序"""
    pass

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        if __doc__ is not None:
            print(__doc__.strip())
        else:
            print("Usage: " + sys.argv[0] + " [options]")
        sys.exit(0)

    main()

