#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/02/24 18:30:33
# @modified 2021/10/07 00:23:22
import sys
import os
import argparse

def unfold(dirname, confirmed = False, prefix_flag = True, print_info = True):
    count = 0
    errors = []

    for root, dirs, files in os.walk(dirname):
        for fname in files:
            fpath = os.path.join(root, fname)
            if prefix_flag:
                prefix = root.replace("/", "_")
                
                if root == ".":
                    prefix = ""
                elif prefix[-1] != "_":
                    prefix += "_"
                
                new_name = prefix + fname
                new_name = new_name.lstrip("._")
            else:
                new_name = fname

            if print_info:
                print("[%03d] 源文件: %s" % (count+1, fpath))
                print("      新文件: %s" % new_name)

            if os.path.exists(new_name):
                print("    错误: 文件已经存在: %s" % new_name)
                errors.append(fpath)

            print("")
            count += 1
            if confirmed:
                os.rename(fpath, new_name)

    if confirmed == False:
        print("发现{0}个文件可以替换,出现{1}个错误".format(count, len(errors)))
        x = input("是否执行替换?(Y/N):")
        if x.upper() == "Y":
            unfold(dirname, True, prefix_flag, print_info = False)
        else:
            print("取消替换，退出...")

def print_help():
    exe_file = os.path.basename(sys.argv[0])
    print("展开文件夹里的文件，使用方式如下:")
    print("")
    print("$> {} 文件路径".format(exe_file))
    print("")

def main():
    if len(sys.argv) == 1:
        print_help()
        return
    parser = argparse.ArgumentParser(description = "展开文件夹里的文件")
    parser.add_argument("path", help = "要展开的文件夹")
    parser.add_argument("--prefix", help = "是否需要前缀", default = "true")
    args   = parser.parse_args(sys.argv[1:])
    prefix_flag = (args.prefix == "true")
    unfold(args.path, prefix_flag = prefix_flag)

if __name__ == '__main__':
    main()