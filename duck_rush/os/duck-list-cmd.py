# -*- coding:utf-8 -*-
"""
列出系统所有可用的命令，支持 Windows / Linux / macOS 三大操作系统。

命令来源包含两类：
1. PATH 环境变量目录中的可执行文件（跨平台，直接扫描文件系统）
2. 当前 shell 的内建命令 / 函数 / 别名（best-effort，依赖 bash 或 PowerShell）

说明：
- Windows 下“可执行文件”依据 PATHEXT 环境变量判定（.exe/.bat/.cmd 等），
  输出时去掉可执行扩展名，与在终端实际调用方式一致。
- Linux / macOS 下“可执行文件”指具有可执行权限的普通文件（os.X_OK）。
- shell 内建命令通过 bash 的 `compgen -c`（或 PowerShell 的 `Get-Command`）收集，
  若当前环境无对应 shell 则自动跳过，仅保留 PATH 中的命令。
"""
import os
import sys
import argparse
import subprocess
from typing import Optional


def is_windows() -> bool:
    return os.name == "nt"


def get_path_dirs() -> list:
    """返回 PATH 中的目录列表（保留顺序并去重）"""
    path_env = os.environ.get("PATH", "")
    if not path_env:
        return []
    sep = ";" if is_windows() else ":"
    dirs = []
    for d in path_env.split(sep):
        d = d.strip()
        if d and d not in dirs:
            dirs.append(d)
    return dirs


def get_windows_executable_exts() -> set:
    """返回 Windows 下被视为可执行文件的扩展名集合（小写，含点）"""
    pathext = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD")
    exts = set()
    for e in pathext.split(";"):
        e = e.strip().lower()
        if e:
            exts.add(e)
    return exts


def is_path_command(fpath: str, exec_exts: Optional[set] = None) -> bool:
    """判断文件是否为 PATH 中的可执行命令"""
    if not os.path.isfile(fpath):
        return False
    if is_windows():
        ext = os.path.splitext(fpath)[1].lower()
        return ext in (exec_exts or get_windows_executable_exts())
    # Linux / macOS：具有可执行权限的普通文件
    return os.access(fpath, os.X_OK)


def collect_path_commands() -> dict:
    """扫描 PATH 目录，返回 {规范化名: (原始名, 完整路径)}，按 PATH 顺序去重。

    Windows 下去重与排序不区分大小写；POSIX 下区分大小写。
    """
    commands: dict = {}
    exec_exts = get_windows_executable_exts() if is_windows() else None

    for d in get_path_dirs():
        if not os.path.isdir(d):
            continue
        try:
            entries = os.listdir(d)
        except (PermissionError, OSError):
            # 无权限或目录不可访问时跳过
            continue

        for fname in entries:
            fpath = os.path.join(d, fname)
            if not is_path_command(fpath, exec_exts):
                continue

            name = fname
            if is_windows():
                # 去掉可执行扩展名，终端调用时通常不带扩展名
                ext = os.path.splitext(fname)[1].lower()
                if ext in exec_exts:
                    name = fname[: -len(ext)]

            key = name.lower() if is_windows() else name
            if key not in commands:
                commands[key] = (name, fpath)
    return commands


def collect_shell_commands() -> set:
    """收集 shell 内建命令 / 函数 / 别名（best-effort）"""
    if is_windows():
        return _collect_powershell_commands()
    return _collect_unix_shell_commands()


def _collect_powershell_commands() -> set:
    cmd = [
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "Get-Command | ForEach-Object { $_.Name }",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return set()
    if out.returncode != 0:
        return set()
    names = set()
    for line in out.stdout.splitlines():
        line = line.strip()
        if line:
            names.add(line)
    return names


def _collect_unix_shell_commands() -> set:
    # 优先使用 bash 的 compgen（覆盖内建命令/关键字/函数/别名/PATH 可执行文件）
    for shell in ("bash", "zsh"):
        cmd = [shell, "-c", "compgen -c"]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        if out.returncode == 0:
            names = set()
            for line in out.stdout.splitlines():
                line = line.strip()
                if line:
                    names.add(line)
            return names
    return set()


def collect_commands() -> dict:
    """合并 PATH 命令与 shell 命令，返回 {规范化名: (原始名, 完整路径或None)}。

    PATH 中的命令优先保留完整路径；仅存在于 shell 的命令路径记为 None。
    """
    commands = collect_path_commands()
    for name in collect_shell_commands():
        key = name.lower() if is_windows() else name
        if key not in commands:
            commands[key] = (name, None)
    return commands


def filter_commands(commands: dict, pattern: Optional[str] = None) -> list:
    """按名称子串过滤（不区分大小写），返回排序后的 [(name, path), ...]"""
    if pattern:
        p = pattern.lower()
        items = [(n, p_) for (n, p_) in commands.values() if p in n.lower()]
    else:
        items = list(commands.values())
    items.sort(key=lambda x: x[0].lower() if is_windows() else x[0])
    return items


def main(pattern: Optional[str] = None,
         show_path: bool = False,
         show_dir: bool = False,
         count: bool = False) -> None:
    """列出系统所有可用的命令"""
    commands = collect_commands()
    items = filter_commands(commands, pattern)

    if count:
        print(len(items))
        return

    for name, fpath in items:
        if show_path:
            if fpath:
                print("%s -> %s" % (name, fpath))
            else:
                print("%s (builtin)" % name)
        elif show_dir:
            if fpath:
                print("%s\t%s" % (name, os.path.dirname(fpath)))
            else:
                print(name)
        else:
            print(name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="列出系统所有可用的命令（支持 Windows / Linux / macOS）")
    parser.add_argument("--name", type=str, default=None,
                        help="按名称子串过滤（不区分大小写）")
    parser.add_argument("--path", action="store_true",
                        help="显示命令对应的完整路径")
    parser.add_argument("--dir", action="store_true",
                        help="显示命令所在的目录")
    parser.add_argument("--count", action="store_true",
                        help="只打印命令总数")
    args = parser.parse_args()
    main(args.name, args.path, args.dir, args.count)
