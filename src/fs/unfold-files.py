# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/02/24 18:30:33
# @modified 2020/02/24 18:35:41
import sys
import os
import argparse

def unfold(dirname, confirmed = False, prefix_flag = True):
    for root, dirs, files in os.walk(dirname):
        for fname in files:
            fpath = os.path.join(root, fname)
            if prefix_flag:
                prefix = root.replace("/", "~")
                if prefix[-1] != "~":
                    prefix += "~"
                new_name = prefix + fname
            else:
                new_name = fname
            print(new_name)
            if confirmed:
                os.rename(fname, new_name)

def main():
    parser = argparse.ArgumentParser(description = "展开文件夹里的文件")
    parser.add_argument("path", help = "要展开的文件夹")
    args   = parser.parse_args(sys.argv[1:])
    main(args.path)

if __name__ == '__main__':
    main()