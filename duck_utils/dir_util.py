# -*- coding:utf-8 -*-
# @filename duck_utils/dir_util.py
# @description 目录遍历与目录筛选的共享工具: 搜索类命令(duck-list-func /
#              duck-find-symbol / duck-find-assign 等)统一用它实现
#              "指定目录(-d) / 排除目录(-x)" 能力, 避免各脚本重复实现。
#
# 用法:
#   parser = argparse.ArgumentParser()
#   add_dir_filter_args(parser)
#   args = parser.parse_args()
#   files = walk_dir(root, accept, dir_filter_from_args(args))

import argparse
import os
import sys
from fnmatch import fnmatch
from typing import Any, Callable, Iterable, List, Optional, FrozenSet

# 目录递归时默认跳过的目录名(依赖/构建产物等)
DEFAULT_IGNORE_DIRS: FrozenSet[str] = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".tox",
    "dist", "build", ".idea", ".vscode", "site-packages", ".mypy_cache",
    ".svn",
})


def split_patterns(values: Optional[List[str]]) -> List[str]:
    """展开目录模式: 兼容重复传参与逗号分隔, 如 ['src,lib', 'test'] -> ['src', 'lib', 'test']"""
    result: List[str] = []
    for value in values or []:
        for part in value.split(","):
            part = part.strip().replace("\\", "/").strip("/")
            if part:
                result.append(part)
    return result


def match_dir_patterns(relpath: str, name: str, patterns: List[str]) -> bool:
    """判断目录是否命中任一模式: 支持目录名、相对路径(以 '/' 分隔)与 fnmatch 通配"""
    for pat in patterns:
        if fnmatch(name, pat) or fnmatch(relpath, pat):
            return True
        if relpath.startswith(pat + "/"):
            return True
    return False


class DirFilter:
    """目录遍历的筛选条件: 忽略(ignore) / 只含(include) / 排除(exclude)。

    - ignore: 命中即不再深入(默认 DEFAULT_IGNORE_DIRS)
    - include: 非空时, 只收录命中目录(含其子目录)下的文件
    - exclude: 命中即跳过该目录(优先级与 ignore 相同)
    """

    def __init__(self, include_dirs: Optional[List[str]] = None,
                 exclude_dirs: Optional[List[str]] = None,
                 ignore_dirs: Optional[Iterable[str]] = None):
        self.include_dirs = include_dirs or []
        self.exclude_dirs = exclude_dirs or []
        self.ignore_dirs = (frozenset(ignore_dirs) if ignore_dirs is not None
                            else DEFAULT_IGNORE_DIRS)

    def should_skip(self, relpath: str, name: str) -> bool:
        """该目录是否应跳过(不进入)"""
        if name in self.ignore_dirs:
            return True
        return match_dir_patterns(relpath, name, self.exclude_dirs)

    def is_included(self, relpath: str, name: str, parent_included: bool) -> bool:
        """进入该目录后, 其(及子目录)下的文件是否纳入结果"""
        if parent_included:
            return True
        return not self.include_dirs or match_dir_patterns(relpath, name, self.include_dirs)


def walk_dir(root: str, accept: Callable[[str], bool],
             dir_filter: Optional[DirFilter] = None) -> List[str]:
    """递归遍历 root, 返回使 accept(文件路径) 为 True 的文件列表。

    不跟随符号链接(避免软链成环); 目录是否进入/收录由 dir_filter 决定。
    """
    df = dir_filter or DirFilter()
    result: List[str] = []

    def _walk(dirpath: str, relpath: str, included: bool) -> None:
        try:
            with os.scandir(dirpath) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError as e:
            sys.stderr.write("walk_dir: %s: %s\n" % (dirpath, e))
            return

        for entry in entries:
            child_rel = f"{relpath}/{entry.name}" if relpath else entry.name
            if entry.is_dir(follow_symlinks=False):
                if df.should_skip(child_rel, entry.name):
                    continue
                _walk(entry.path, child_rel, df.is_included(child_rel, entry.name, included))
            elif entry.is_file(follow_symlinks=False) and included:
                if accept(entry.path):
                    result.append(entry.path)

    root_name = os.path.basename(os.path.normpath(root))
    _walk(root, "", df.is_included("", root_name, False))
    return result


def add_dir_filter_args(parser: argparse.ArgumentParser) -> None:
    """给搜索类命令统一添加 -d/--dir 与 -x/--exclude-dir 两个目录筛选参数"""
    parser.add_argument("-d", "--dir", action="append", metavar="PATTERN",
                        help="只搜索命中的目录(可重复传参或用逗号分隔, 如 -d src,lib); "
                             "按目录名或相对路径匹配, 支持 * 通配")
    parser.add_argument("-x", "--exclude-dir", action="append", metavar="PATTERN",
                        help="排除命中的目录(可重复传参或用逗号分隔, 如 -x test,dist); "
                             "按目录名或相对路径匹配, 支持 * 通配")


def dir_filter_from_args(args: Any) -> DirFilter:
    """从命令行参数(需先经 add_dir_filter_args 注册)构造 DirFilter"""
    return DirFilter(include_dirs=split_patterns(getattr(args, "dir", None)),
                     exclude_dirs=split_patterns(getattr(args, "exclude_dir", None)))
