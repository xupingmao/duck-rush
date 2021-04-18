#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/04/18 17:00:00
# @modified 2021/04/18 17:04:08
# @filename config-shell-path.py

import os
import sys
import argparse

HOME_PATH  = os.environ["HOME"]

def find_bash_profile_path():
    bash_profile = os.path.join(HOME_PATH, ".bash_profile")
    if os.path.exists(bash_profile):
        return bash_profile

    bash_rc = os.path.join(HOME_PATH, ".bashrc")
    if os.path.exists(bash_rc):
        return bash_rc
    raise Exception("bash profile not found!")

def load_bash_profile():
    fpath = find_bash_profile_path()
    with open(fpath) as fp:
        return fp.read()

def append_to_bash_profile(cmd):
    fpath = find_bash_profile_path()
    bash_profile_text = load_bash_profile()

    if cmd in bash_profile_text:
        return

    with open(fpath, "a+") as fp:
        fp.write("\n")
        fp.write(cmd)

def add_shell_path(fpath):
    fpath = os.path.abspath(fpath)
    os.system("chmod -R +x %s" % fpath)

    cmd = "PATH=$PATH:%s" % fpath
    append_to_bash_profile(cmd)

def makedirs(dirname):
    '''检查并创建目录(如果不存在不报错)'''
    if not os.path.exists(dirname):
        os.makedirs(dirname)
        return True
    return False

def main():
    parser = argparse.ArgumentParser(description = "添加PATH路径")
    parser.add_argument("path", help = "需要添加的PATH")
    args   = parser.parse_args()

    abspath = os.path.abspath(args.path)
    if not os.path.exists(abspath):
        print("无效的路径:", abspath)
        sys.exit(1)

    add_shell_path(abspath)

if __name__ == '__main__':
    main()
