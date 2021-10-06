#!/usr/bin/env python3
import os

FILE_PATH  = os.path.abspath(__file__)
HOME_PATH  = os.environ["HOME"]
DIR_PATH   = os.path.dirname(FILE_PATH)
SRC_PATH   = os.path.join(DIR_PATH, "./src")
LOCAL_PATH = os.path.join(DIR_PATH, "./local")
CONFIG_PATH = os.path.join(DIR_PATH, "./config")

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

def add_alias_config():
    code = "source %s" % os.path.join(CONFIG_PATH, "duck-alias.sh")
    append_to_bash_profile(code)

def do_install():
    print("准备安装duck_rush ... ")
    for fname in os.listdir(SRC_PATH):
        fpath = os.path.join(SRC_PATH, fname)
        if os.path.isdir(fpath):
            add_shell_path(fpath)


    # 本地的一些临时脚本
    makedirs(LOCAL_PATH)
    add_shell_path(LOCAL_PATH)
    add_alias_config()

    print("安装完成!")

if __name__ == '__main__':
    do_install()


