# -*- coding:utf-8 -*-
# @author mark
# @since 2022/03/30 19:12:02
# @modified 2022/03/30 19:15:05
# @filename file-touch.py
import argparse
import os

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="文件名")
    args = parser.parse_args()

    fpath = args.filename

    if not os.path.exists(fpath):
        with open(fpath, "a+"):
            pass


if __name__ == '__main__':
    main()