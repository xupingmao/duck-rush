# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/09/10
# @filename duck-unzip.py
# @description 解压 zip 压缩包（基于标准库 zipfile，防路径穿越）
"""duck-unzip —— 解压 zip 压缩包。

用法:
  duck-unzip <压缩包.zip> [选项]

选项:
  -d, --dir DIR      解压到指定目录（默认当前目录）
  -l, --list         只列出内容，不解压
  -p, --pattern GLOB 只解压匹配通配符的条目，如 "*.py"（可重复指定）
  -o, --overwrite    覆盖已存在的文件（默认跳过）
  -q, --quiet        不输出解压进度
  --encoding NAME    对乱码文件名使用的编码（默认尝试 gbk）
  -h, --help         显示本帮助

安全: 会自动拒绝 ../ 这类路径穿越的条目（zip slip）。
"""

import sys
import os
import fnmatch
import zipfile
import argparse
from typing import List, Optional

FALLBACK_ENCODINGS = ["gbk", "cp437", "shift_jis"]


def fix_name(name: str, encoding: str) -> str:
    """修正未标记 UTF-8 的中文文件名"""
    try:
        name.encode("cp437")
    except UnicodeEncodeError:
        return name
    for enc in [encoding] + FALLBACK_ENCODINGS:
        try:
            return name.encode("cp437").decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return name


def is_unsafe(name: str) -> bool:
    """判断条目是否存在路径穿越风险"""
    if name.startswith("/") or name.startswith("\\"):
        return True
    if ":" in name.split("/")[0]:
        return True
    return ".." in name.replace("\\", "/").split("/")


def safe_target(dest: str, name: str) -> Optional[str]:
    """计算解压目标路径, 越界或非法时返回 None"""
    if is_unsafe(name):
        return None
    target = os.path.normpath(os.path.join(dest, name))
    dest_root = os.path.normpath(os.path.abspath(dest))
    target_root = os.path.normpath(os.path.abspath(target))
    if not (target_root == dest_root
            or target_root.startswith(dest_root + os.sep)):
        return None
    return target


def match_patterns(name: str, patterns: List[str]) -> bool:
    """判断条目名是否命中任一通配符, 未指定通配符时全部命中"""
    if not patterns:
        return True
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def do_list(zip_path: str, encoding: str) -> int:
    """列出压缩包内容"""
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = fix_name(info.filename, encoding)
            date = "%04d-%02d-%02d %02d:%02d" % info.date_time[:5]
            flag = "D" if info.is_dir() else "F"
            print("%s %10d %s  %s" % (flag, info.file_size, date, name))
        print("共 %d 项" % len(zf.infolist()))
    return 0


def do_extract(zip_path: str, dest: str, patterns: List[str],
               overwrite: bool, quiet: bool, encoding: str) -> int:
    """解压压缩包到 dest"""
    os.makedirs(dest, exist_ok=True)

    extracted = 0
    skipped = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = fix_name(info.filename, encoding)
            if not match_patterns(name, patterns):
                continue

            target = safe_target(dest, name)
            if target is None:
                print("跳过不安全的条目: %s" % name, file=sys.stderr)
                skipped += 1
                continue

            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue

            if os.path.exists(target) and not overwrite:
                if not quiet:
                    print("已存在, 跳过: %s" % name)
                skipped += 1
                continue

            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    dst.write(chunk)
            extracted += 1
            if not quiet:
                print("解压: %s" % name)

    print("解压完成: %d 个文件, 跳过 %d 项 -> %s" % (extracted, skipped, dest))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="解压 zip 压缩包")
    parser.add_argument("zipfile", help="压缩包路径")
    parser.add_argument("-d", "--dir", default=".", help="解压目标目录（默认当前目录）")
    parser.add_argument("-l", "--list", action="store_true", help="只列出内容")
    parser.add_argument("-p", "--pattern", action="append", default=[],
                        help="只解压匹配通配符的条目，可重复指定")
    parser.add_argument("-o", "--overwrite", action="store_true",
                        help="覆盖已存在的文件")
    parser.add_argument("-q", "--quiet", action="store_true", help="不输出解压进度")
    parser.add_argument("--encoding", default="gbk",
                        help="对乱码文件名使用的编码（默认 gbk）")
    args = parser.parse_args(argv)

    if not os.path.exists(args.zipfile):
        print("文件不存在: %s" % args.zipfile, file=sys.stderr)
        return 1

    try:
        if args.list:
            return do_list(args.zipfile, args.encoding)
        return do_extract(args.zipfile, args.dir, args.pattern,
                          args.overwrite, args.quiet, args.encoding)
    except zipfile.BadZipFile as e:
        print("压缩包损坏: %s (%s)" % (args.zipfile, e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
