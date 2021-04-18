# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/02/25 12:34:29
# @modified 2020/03/02 12:20:17
import sys
import argparse
import os
import time
import traceback

EXECTABLE_FILE_EXT_SET = set([
    ".py", 
    ".sh", ".command", 
    ".bat", 
    ".exe",
    ".js",   # NodeJS
])

PATH_ESCAPE_CHARS = "^[]@*$!<> "

def print_red(msg):
    print("\033[31m\033[01m%s\033[0m" % msg, end = '')


def print_blue(msg):
    print("\033[34m\033[01m%s\033[0m" % msg, end = '')


def print_green(msg):
    print("\033[32m\033[01m%s\033[0m" % msg, end = '')


def print_lightblue(msg):
    print("\033[36m%s\033[0m" % msg, end = '')

def escape_arg(path):
    i = 0
    target = ''
    for c in path:
        if c in PATH_ESCAPE_CHARS:
            target += '\\' + c
        else:
            target += c
    return target

def log_debug(*args):
    print_lightblue("[DEBUG]")
    print(*args)
    # print("\033[36m[DEBUG]\033[0m", *args)

class DuckCommand:

    def __init__(self, fpath):
        self.fpath = fpath
        self.fname  = os.path.basename(fpath)
        self.name, self.ext = os.path.splitext(self.fname)

    def match(self, name):
        # TODO 相似度>90%
        return self.name.find(name) >= 0

    def execute(self, args):
        args = " ".join([escape_arg(arg) for arg in args])
        if self.ext == ".py":
            os.system("python3 %s %s" % (escape_arg(self.fpath), args))
        # print("execute %s" % self.fpath)

def is_executable_file(fpath):
    name, ext = os.path.splitext(fpath)
    return ext in EXECTABLE_FILE_EXT_SET

def get_command_list():
    duck_dir = os.path.dirname(__file__)
    src_dir  = os.path.join(duck_dir, "src")
    command_list = []
    for root, dirs, files in os.walk(src_dir):
        for fname in files:
            if is_executable_file(fname):
                fpath = os.path.join(root, fname)
                command_list.append(DuckCommand(fpath))
    return command_list


def list_command_func(args):
    commands = get_command_list()
    for cmd in commands:
        print(cmd.fpath)

def install_func(args):
    profile_name = ".bash_profile"
    home_path = os.environ["HOME"]
    profile_path = os.path.join(home_path, profile_name)
    print("install to [%s]" % profile_path)

    with open(profile_path) as fp:
        content = fp.read()

    fpath = os.path.abspath(__file__)
    alias_instruction = 'alias duck="python3 %s"' % fpath
    if alias_instruction not in content:
        with open(profile_path, mode = "a+") as fp:
            fp.write("\n" + alias_instruction + "\n")

def help_func(args):
    PARSER.print_help()

def default_func(args):
    action = args.action
    log_debug(args)
    commands = get_command_list()
    matches  = []
    for cmd in commands:
        if cmd.match(action):
            matches.append(cmd)

    if len(matches) == 0:
        print("No command found")
        return

    if len(matches) == 1:
        return matches[0].execute(args.args)

    print("found multi commands:")
    for index, cmd in enumerate(matches):
        print("%02d: %s" % (index, cmd.name))

    choice = input("please choose:")




ACTION_FUNC_DICT = {
    "list": list_command_func,
    "install": install_func,
    "help": help_func,
}

PARSER = argparse.ArgumentParser(description = "工具集入口")
PARSER.add_argument("action", nargs = "?", help = "操作", default = "help")
PARSER.add_argument("args", nargs = "*", help = "参数")

def main():
    args   = PARSER.parse_args()
    func = ACTION_FUNC_DICT.get(args.action, default_func)
    func(args)

if __name__ == '__main__':
    main()