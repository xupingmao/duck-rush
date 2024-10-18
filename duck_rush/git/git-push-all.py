# -*- coding:utf-8 -*-
"""
@Author       : xupingmao
@email        : 578749341@qq.com
@Date         : 2023-02-05 13:48:09
@LastEditors  : xupingmao
@LastEditTime : 2023-02-05 13:59:45
@FilePath     : /xnoted:/projects/duck_rush/src/git/git-push-all.py
@Description  : 描述
"""

import os
import sys
import fire

try:
    import termcolor
    def yellow_text(text):
        return termcolor.colored(text, "yellow")
except ImportError:
    def yellow_text(text):
        return text

def list_remote():
    result = os.popen("git remote").read()
    parts = result.split()
    return list(filter(lambda x:x.strip()!="", parts))

def exec_cmd(cmd="", do_print=True):
    if do_print:
        print(yellow_text(f"[executing]: {cmd}"))
    os.system(cmd)

def push_all(actions=set()):
    """推送到所有的远端

    操作选项:
    * with-tags 推送所有的tag
    """
    remote_list = list_remote()
    print("检测到远端配置: %s" % remote_list)
    for remote in remote_list:
        # print("准备推送到 %s ..." % remote)
        exec_cmd(f"git push {remote}")
        if "with-tags" in actions:
            exec_cmd(f"git push {remote} --tags")
    
def check_git():
    ret = os.system("git --version")
    if ret != 0:
        print("没有检测到git环境，请先安装")
        sys.exit(1)

if __name__ == "__main__":
    check_git()
    fire.Fire(push_all)
