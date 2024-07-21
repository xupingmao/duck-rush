# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2023-12-23 12:09:14
LastEditors: xupingmao
LastEditTime: 2024-07-21 19:08:37
FilePath: /duck_rush/duck_rush/git/git-count-lines.py
Description: 描述
'''
# encoding=utf-8
import typing
import os
import subprocess
import fire

def my_popen(cmd, debug=False):
    if debug:
        print(f"DEBUG: cmd: {cmd}")
    proc = subprocess.Popen(cmd,
                            shell=True,
                            stdout=subprocess.PIPE)
    return proc.stdout

class GitLogInfo:
    def __init__(self, user_name="", add=0, sub=0, loc=0):
        self.user_name=user_name
        self.add = add
        self.sub = sub
        self.loc = loc

def main(encoding="utf-8", debug=False, sort=False):
    fp = my_popen("git log --format=%aN", debug=debug)
    user_set = set()
    for line in fp.readlines():
        user_name = line.decode(encoding)
        user_set.add(user_name.strip())
    
    users = sorted(user_set)
    git_logs: typing.List[GitLogInfo] = []

    for user_name in users:
        stats_fp = my_popen(f"git log --author=\"{user_name}\" --pretty=tformat: --numstat", debug=debug)
        add = 0
        sub = 0
        loc = 0
        for num_line in stats_fp.readlines():
            num_line = num_line.decode(encoding)
            parts = num_line.split()
            if len(parts) < 3:
                continue
            if parts[0] == "-" or parts[1] == "-":
                continue
            a = int(parts[0])
            b = int(parts[1])
            fname = parts[2]
            if fname == "go.sum":
                continue
            add += a
            sub += b
            loc += a - b
        if sort:
            git_logs.append(GitLogInfo(user_name=user_name, add=add, sub=sub, loc=loc))
        else:
            print(f"{user_name}: added lines: {add}, removed lines: {sub}, total lines: {loc}")

    if sort:
        git_logs.sort(key=lambda x:x.loc, reverse=True)
        for item in git_logs:
            print(f"{item.user_name}: added lines: {item.add}, removed lines: {item.sub}, total lines: {item.loc}")

if __name__ == "__main__":
    fire.Fire(main)
    
