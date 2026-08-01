# -*- coding: utf-8 -*-
# @author xupingmao
# @since 2026/08/01
# @filename duck-which.py
# @description 复刻 which: 在 PATH 中查找可执行文件; Windows 下名称无后缀时自动匹配 PATHEXT 各后缀

import argparse
import os
import sys
from typing import List, Optional, Set

from duck_utils.os_util import is_windows


def _pathext_set() -> Set[str]:
    """返回 Windows 可执行后缀集合(小写, 含点), 缺省取系统常见后缀。"""
    raw = os.environ.get("PATHEXT", "")
    if raw:
        exts = [e for e in raw.split(";") if e]
    else:
        exts = [".COM", ".EXE", ".BAT", ".CMD", ".VBS", ".VBE", ".JS",
                ".JSE", ".WSF", ".WSH", ".MSC"]
    return {e.lower() for e in exts}


_PATHEXT: Set[str] = _pathext_set()


def _path_dirs() -> List[str]:
    """按 os.pathsep 拆分 PATH, 忽略空项。"""
    raw = os.environ.get("PATH", "")
    return [d for d in raw.split(os.pathsep) if d]


def _candidate_names(base: str) -> List[str]:
    """在单个目录内要尝试的文件名列表。

    - 名称已含扩展名: 只试原名
    - 名称无扩展名且为 Windows: 先试无后缀本体, 再依次试 PATHEXT 各后缀
    - 名称无扩展名且非 Windows: 只试原名
    """
    if os.path.splitext(base)[1]:
        return [base]
    if is_windows():
        cands = [base]
        for ext in _PATHEXT:
            cands.append(base + ext)
        return cands
    return [base]


def _is_executable(path: str) -> bool:
    """判断路径是否为可执行的常规文件。"""
    if not os.path.isfile(path):
        return False
    if is_windows():
        # Windows 按扩展名判定可执行; 无后缀文件(如脚本)也允许匹配
        ext = os.path.splitext(path)[1].lower()
        return ext in _PATHEXT or ext == ""
    return os.access(path, os.X_OK)


def _find(name: str, all_matches: bool) -> List[str]:
    """在 PATH(或给定目录)中查找 name 的可执行文件, 返回匹配路径列表。"""
    has_dir = (os.path.sep in name) or (
        os.altsep is not None and os.altsep in name)
    if has_dir:
        search_dirs = [os.path.dirname(name) or "."]
        base = os.path.basename(name)
    else:
        search_dirs = _path_dirs()
        base = name

    cands = _candidate_names(base)
    results = []
    seen = set()  # type: Set[str]
    for d in search_dirs:
        for c in cands:
            p = os.path.join(d, c)
            if p in seen:
                continue
            if _is_executable(p):
                seen.add(p)
                results.append(p)
                if not all_matches:
                    return results
    return results


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="复刻 which: 在 PATH 中查找可执行文件。"
                    "Windows 下若名称无扩展名, 自动尝试 PATHEXT 中各后缀"
                    "(.exe/.bat/.cmd...), 如 duck-which duck-time 可匹配 "
                    "duck-time / duck-time.exe / duck-time.bat / duck-time.cmd。")
    parser.add_argument("names", nargs="+",
                        help="要查找的命令名称(可一次指定多个)")
    parser.add_argument("-a", "--all", action="store_true",
                        help="列出所有匹配项, 而不仅是第一个")
    args: argparse.Namespace = parser.parse_args()

    found_any = False
    for name in args.names:
        matches = _find(name, args.all)
        for m in matches:
            print(m)
        if matches:
            found_any = True

    # 与 which 一致: 找到至少一个则退出码 0, 否则 1
    sys.exit(0 if found_any else 1)


if __name__ == "__main__":
    main()
