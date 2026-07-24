# -*- coding:utf-8 -*-
"""
duck-rm —— 复刻 Linux 下 rm 命令的基础能力，供 Windows 系统使用。

复刻的行为：
- 删除普通文件 / 符号链接（仅移除链接本身，绝不会跟随删除链接指向的目标）
- -r / -R：递归删除目录及其内容
- -f / --force：忽略不存在的文件、不交互询问、强制删除只读文件
- -i / --interactive：删除前逐一对每个文件/目录询问确认
- -v / --verbose：输出 removed 'path'（与 Linux rm 一致）
- 退出码：全部成功为 0，任意一项失败为 1

Windows 专属处理：
- 删除前自动清除只读属性（os.chmod S_IWRITE），从而像 Linux 一样能直接删除只读文件
- 正确处理符号链接，避免误删链接目标

注意：-f 与 -i 同时指定时，以命令行中最后出现的为准（与 GNU rm 行为一致）。
"""
import os
import sys
import stat
import argparse


had_error: bool = False


def error(msg: str) -> None:
    global had_error
    had_error = True
    print("rm: %s" % msg, file=sys.stderr)


def _clear_readonly(path: str) -> None:
    """Windows 下删除前清除只读属性；POSIX 无需处理。"""
    if os.name != "nt":
        return
    try:
        os.chmod(path, stat.S_IWRITE)
    except OSError:
        pass


def _is_reparse_point(path: str) -> bool:
    """Windows 下判断是否为重解析点（符号链接或目录 junction 均属此类）。

    os.path.islink 对 junction 返回 False，因此必须额外检测，避免把 junction
    当成普通目录递归进入、误删其指向的目标内容。
    """
    if os.name != "nt":
        return False
    try:
        st = os.lstat(path)
        return bool(st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return False


def _prompt(path: str, kind: str) -> bool:
    try:
        ans = input("rm: remove %s '%s'? " % (kind, path))
    except (EOFError, KeyboardInterrupt):
        return False
    return ans.strip().lower() in ("y", "yes")


def _last_opt_index(tokens: tuple) -> int:
    """返回命令行中某个选项（含 -rf 合并写法）最后出现的位置，用于 -f/-i 优先级判定。"""
    last = -1
    for i, arg in enumerate(sys.argv):
        if arg in tokens:
            last = i
        elif len(arg) > 2 and arg.startswith("-") and not arg.startswith("--"):
            # 合并短选项，如 -rf 中的 f
            for t in tokens:
                if len(t) == 2 and t[1] in arg[1:]:
                    last = i
    return last


def _resolve_mode(force: bool, interactive: bool) -> str:
    """force / interactive 同时指定时，以命令行中最后出现的为准。"""
    if not (force or interactive):
        return "default"
    f_idx = _last_opt_index(("-f", "--force"))
    i_idx = _last_opt_index(("-i", "--interactive"))
    if f_idx > i_idx:
        return "force"
    if i_idx > f_idx:
        return "interactive"
    return "force" if force else "interactive"


def _remove_link(path: str, mode: str, verbose: bool) -> bool:
    if mode == "interactive" and not _prompt(path, "symbolic link"):
        return False
    _clear_readonly(path)
    try:
        os.unlink(path)
    except IsADirectoryError:
        # 目录符号链接 / junction 需用 rmdir 移除链接本身
        os.rmdir(path)
    if verbose:
        print("removed '%s'" % path)
    return True


def _remove_file(path: str, mode: str, verbose: bool) -> bool:
    if mode == "interactive" and not _prompt(path, "regular file"):
        return False
    _clear_readonly(path)
    try:
        os.unlink(path)
    except IsADirectoryError:
        error("cannot remove '%s': Is a directory" % path)
        return False
    if verbose:
        print("removed '%s'" % path)
    return True


def _remove_dir(path: str, mode: str, verbose: bool, recursive: bool) -> bool:
    # 自底向上删除子项
    try:
        with os.scandir(path) as it:
            entries = list(it)
    except OSError as e:
        error("cannot remove '%s': %s" % (path, e.strerror))
        return False

    all_ok = True
    for entry in entries:
        if entry.is_symlink() or _is_reparse_point(entry.path):
            ok = _remove_link(entry.path, mode, verbose)
        elif entry.is_dir(follow_symlinks=False):
            ok = _remove_dir(entry.path, mode, verbose, recursive)
        else:
            ok = _remove_file(entry.path, mode, verbose)
        if not ok:
            all_ok = False

    if mode == "interactive" and not _prompt(path, "directory"):
        return False

    _clear_readonly(path)
    try:
        os.rmdir(path)
    except OSError as e:
        error("cannot remove '%s': %s" % (path, e.strerror))
        return False

    if verbose and all_ok:
        print("removed directory '%s'" % path)
    return all_ok


def _remove_entry(path: str, mode: str, verbose: bool, recursive: bool) -> bool:
    if os.path.islink(path) or _is_reparse_point(path):
        return _remove_link(path, mode, verbose)
    if os.path.isdir(path):
        if not recursive:
            error("cannot remove '%s': Is a directory" % path)
            return False
        return _remove_dir(path, mode, verbose, recursive)
    return _remove_file(path, mode, verbose)


def remove_path(path: str, recursive: bool, mode: str, verbose: bool) -> bool:
    if not os.path.lexists(path):
        if mode == "force":
            return True
        error("cannot remove '%s': No such file or directory" % path)
        return False
    return _remove_entry(path, mode, verbose, recursive)


def main(paths: list,
         recursive: bool = False,
         force: bool = False,
         interactive: bool = False,
         verbose: bool = False) -> None:
    """复刻 Linux rm 的基础删除能力"""
    mode = _resolve_mode(force, interactive)
    for path in paths:
        remove_path(path, recursive, mode, verbose)

    if had_error:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="复刻 Linux rm 的基础能力（用于 Windows）")
    parser.add_argument("paths", nargs="+", help="要删除的文件或目录")
    parser.add_argument("-r", "-R", "--recursive", action="store_true",
                        help="递归删除目录及其内容")
    parser.add_argument("-f", "--force", action="store_true",
                        help="忽略不存在的文件、不询问、删除只读文件")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="删除前逐个询问确认")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="显示被删除的路径（removed 'path'）")
    args = parser.parse_args()
    main(args.paths, args.recursive, args.force, args.interactive, args.verbose)
