# -*- coding:utf-8 -*-
# @author xupingmao
# @filename duck-xargs.py
# @description 复刻 xargs 核心功能: 从 stdin 读取条目, 作为命令参数批量执行

import sys
import subprocess


USAGE = """duck-xargs - 复刻 xargs 核心功能

用法:
  duck xargs [选项] 命令 [命令参数...]
  duck xargs [选项] -- 命令 [命令参数...]   (用 -- 显式分隔选项与命令)

从 stdin 读取条目, 作为命令的参数批量执行。选项必须出现在命令之前。

选项:
  -0, --null              以 NUL(\\0) 分隔条目
  -n, --max-args N        每次执行最多使用 N 个条目
  -L, --max-lines N       每 N 行作为一组执行
  -I, --replace STR       将命令中的 STR 替换为每个条目, 每条目单独执行一次
  -d, --delimiter DELIM   使用自定义分隔符
  -t, --verbose           执行前把命令打印到 stderr
  -h, --help              显示本帮助信息并退出

示例:
  printf 'a b c' | duck xargs echo
  find . -name '*.py' -print0 | duck xargs -0 -I {} echo {}
  printf '1 2 3 4' | duck xargs -n 2 echo
"""


def parse_own_args(argv):
    """解析 duck-xargs 自身的选项, 并分离出要执行的命令

    选项必须出现在命令之前; 第一个非选项参数即命令开始,
    其后所有参数都属于该命令(支持 -- 显式分隔)。
    """
    opts = {
        "null": False,       # -0 / --null
        "max_args": None,    # -n / --max-args
        "max_lines": None,   # -L / --max-lines
        "replace": None,     # -I / --replace
        "delim": None,       # -d / --delimiter
        "verbose": False,    # -t / --verbose
    }
    flags_bool = {"-0", "--null", "-t", "--verbose", "-h", "--help"}
    flags_val = {"-n", "--max-args", "-L", "--max-lines",
                 "-I", "--replace", "-d", "--delimiter"}

    command = []
    started = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if not started:
            if a == "--":
                started = True
                i += 1
                continue
            if a in ("-h", "--help"):
                sys.stdout.write(USAGE)
                sys.exit(0)
            if a in flags_bool:
                if a in ("-0", "--null"):
                    opts["null"] = True
                else:
                    opts["verbose"] = True
                i += 1
                continue
            if a in flags_val:
                val = argv[i + 1]
                if a in ("-n", "--max-args"):
                    opts["max_args"] = int(val)
                elif a in ("-L", "--max-lines"):
                    opts["max_lines"] = int(val)
                elif a in ("-I", "--replace"):
                    opts["replace"] = val
                else:
                    opts["delim"] = val
                i += 2
                continue
            # 第一个非选项参数: 命令开始
            started = True
            command.append(a)
            i += 1
            continue
        command.append(a)
        i += 1
    return opts, command


def read_items(opts, raw):
    """根据分隔选项从输入文本中取出条目列表"""
    if opts["delim"] is not None:
        d = opts["delim"]
        if raw.endswith(d):
            raw = raw[: -len(d)]
        return raw.split(d) if raw else []

    # 默认: 任意空白字符切分(类似 str.split)
    return raw.split()


def chunked(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def run_command(cmd, verbose):
    if verbose:
        sys.stderr.write("+ " + " ".join(cmd) + "\n")
    try:
        subprocess.run(cmd)
    except FileNotFoundError:
        sys.stderr.write("duck-xargs: %s: command not found\n" % cmd[0])
    except NotADirectoryError:
        sys.stderr.write("duck-xargs: %s: command not found\n" % cmd[0])


def main():
    opts, command = parse_own_args(sys.argv[1:])
    if not command:
        command = ["echo"]

    verbose = opts["verbose"]
    replace = opts["replace"]

    # 一次性以字节方式读取 stdin, 再按选项解码/切分
    data = sys.stdin.buffer.read()
    raw = data.decode("utf-8", errors="replace")

    if opts["max_lines"] is not None:
        # -L: 按物理行分组, 每行作为一个参数
        base = [ln for ln in raw.split("\n") if ln != ""]
    elif opts["null"]:
        parts = data.split(b"\x00")
        if parts and parts[-1] == b"":
            parts.pop()
        base = [p.decode("utf-8", errors="replace") for p in parts]
    else:
        base = read_items(opts, raw)

    if replace is not None:
        # -I: 每个条目单独执行一次, 并将 replace 替换为该条目
        for item in base:
            cmd = [arg.replace(replace, item) for arg in command]
            run_command(cmd, verbose)
    elif opts["max_lines"] is not None:
        for chunk in chunked(base, opts["max_lines"]):
            run_command(command + chunk, verbose)
    elif opts["max_args"] is not None:
        for chunk in chunked(base, opts["max_args"]):
            run_command(command + chunk, verbose)
    else:
        if base:
            run_command(command + base, verbose)


if __name__ == "__main__":
    main()
