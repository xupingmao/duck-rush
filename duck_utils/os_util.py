# encoding=utf-8
import sys
import subprocess
import os
import platform

def popen(cmd):
    proc = subprocess.Popen(cmd,
                            shell=True,
                            stdout=subprocess.PIPE)
    return proc.stdout

def popen_str(cmd, encoding="utf-8") -> str:
    return popen(cmd).read().decode(encoding=encoding)


def exec_cmd(cmd="", do_print=True):
    if do_print:
        print(cmd)
    os.system(cmd)

def set_console_font_color(color):
    """设置终端的字体颜色"""
    if color == "red":
        sys.stdout.write("\033[31m")
    if color == "green":
        sys.stdout.write("\033[32m")
    if color == "orange":
        sys.stdout.write("\033[33m")
    if color == "blue":
        sys.stdout.write("\033[34m")
    if color == "default":
        sys.stdout.write("\033[0m")


def is_windows():
    return os.name == "nt"

def is_mac():
    return platform.system() == "Darwin"

def is_linux():
    return os.name == "linux"


def get_duck_rush_home() -> str:
    """返回 duck_rush 的用户级根目录 ~/.duck-rush（仅返回路径，不创建）。"""
    return os.path.join(os.path.expanduser("~"), ".duck-rush")


def get_data_dir() -> str:
    """返回命令数据存储根目录 ~/.duck-rush/data（自动创建并返回）。"""
    d = os.path.join(get_duck_rush_home(), "data")
    os.makedirs(d, exist_ok=True)
    return d


def get_command_data_dir(cmd: str) -> str:
    """返回单个命令 {cmd} 的数据目录 ~/.duck-rush/data/{cmd}（自动创建并返回）。

    命令需要持久化运行时数据（缓存、状态文件等）时统一放在这里，
    避免污染仓库或散落各处。
    """
    d = os.path.join(get_data_dir(), cmd)
    os.makedirs(d, exist_ok=True)
    return d

