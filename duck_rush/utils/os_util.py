# encoding=utf-8
import sys
import subprocess

def popen(cmd):
    proc = subprocess.Popen(cmd,
                            shell=True,
                            stdout=subprocess.PIPE)
    return proc.stdout

def popen_str(cmd, encoding="utf-8") -> str:
    return popen(cmd).read().decode(encoding=encoding)


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
