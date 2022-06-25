# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/12/25 12:07:39
# @modified 2021/12/26 21:18:19
# @filename duck-plugin-template.py

import argparse

def main():
    parser = argparse.ArgumentParser(description = "工具的使用介绍")
    parser.add_argument("filename", help="文件名")
    args = parser.parse_args()

if __name__ == '__main__':
    main()
