# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/09/10
# @filename duck-zip.py
# @description 创建 zip 压缩包并查看压缩包内容（基于标准库 zipfile）
"""duck-zip —— 创建 zip 压缩包，或查看压缩包内容。

用法:
  duck-zip <压缩包.zip> <路径...>   把文件或目录打包
  duck-zip -l <压缩包.zip>          列出压缩包内容
  duck-zip -t <压缩包.zip>          检查压缩包是否完整

选项:
  -l, --list       列出压缩包内容（名称、原始大小、压缩后大小、修改时间）
  -t, --test       测试压缩包完整性
  -q, --quiet      不输出打包进度
  --encoding NAME  列出时对乱码文件名使用的编码（默认尝试 gbk）
  -h, --help       显示本帮助

示例:
  duck-zip backup.zip ./src ./README.md
  duck-zip -l backup.zip
"""

import sys
import os
import zipfile
import argparse
from typing import List, Optional

# 部分 Windows 压缩工具不设置 UTF-8 标志位, 文件名按本地编码存储
FALLBACK_ENCODINGS = ["gbk", "cp437", "shift_jis"]


def iter_files(path: str) -> List[str]:
    """展开路径: 文件返回自身, 目录返回其下所有文件的相对形式"""
    if os.path.isfile(path):
        return [path]
    result: List[str] = []
    for dirpath, _dirnames, filenames in os.walk(path):
        for name in filenames:
            result.append(os.path.join(dirpath, name))
    return result


def build_arcname(fpath: str, base: str) -> str:
    """计算文件在压缩包内的名称, 目录打包时去掉外层目录前缀"""
    if os.path.isfile(base):
        return os.path.basename(fpath)
    rel = os.path.relpath(fpath, os.path.dirname(base.rstrip(os.sep)) or ".")
    return rel.replace(os.sep, "/")


def fix_name(name: str, encoding: str) -> str:
    """修正未标记 UTF-8 的中文文件名"""
    try:
        name.encode("cp437")
    except UnicodeEncodeError:
        # 已经是非 ASCII 的正常文件名
        return name
    for enc in [encoding] + FALLBACK_ENCODINGS:
        try:
            return name.encode("cp437").decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return name


def do_create(zip_path: str, paths: List[str], quiet: bool) -> int:
    """把 paths 打包进 zip_path"""
    if os.path.exists(zip_path):
        print("压缩包已存在: %s" % zip_path, file=sys.stderr)
        return 1

    total = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            if not os.path.exists(path):
                print("路径不存在: %s" % path, file=sys.stderr)
                continue
            for fpath in iter_files(path):
                arcname = build_arcname(fpath, path)
                zf.write(fpath, arcname)
                total += 1
                if not quiet:
                    print("adding: %s" % arcname)

    print("已打包 %d 个文件 -> %s" % (total, zip_path))
    return 0


def do_list(zip_path: str, encoding: str) -> int:
    """列出压缩包内容"""
    if not os.path.exists(zip_path):
        print("文件不存在: %s" % zip_path, file=sys.stderr)
        return 1

    with zipfile.ZipFile(zip_path) as zf:
        total_raw = 0
        total_compress = 0
        for info in zf.infolist():
            total_raw += info.file_size
            total_compress += info.compress_size
            name = fix_name(info.filename, encoding)
            date = "%04d-%02d-%02d %02d:%02d" % info.date_time[:5]
            print("%10d %10d %s  %s" % (
                info.file_size, info.compress_size, date, name))
        print("共 %d 项, 原始大小 %d, 压缩后 %d" % (
            len(zf.infolist()), total_raw, total_compress))
    return 0


def do_test(zip_path: str) -> int:
    """检查压缩包完整性"""
    if not os.path.exists(zip_path):
        print("文件不存在: %s" % zip_path, file=sys.stderr)
        return 1

    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        if bad:
            print("损坏的条目: %s" % bad, file=sys.stderr)
            return 1
    print("压缩包完好: %s" % zip_path)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="创建 zip 压缩包或查看压缩包内容")
    parser.add_argument("zipfile", help="压缩包路径")
    parser.add_argument("paths", nargs="*", default=[], help="待打包的文件或目录")
    parser.add_argument("-l", "--list", action="store_true", help="列出压缩包内容")
    parser.add_argument("-t", "--test", action="store_true", help="测试压缩包完整性")
    parser.add_argument("-q", "--quiet", action="store_true", help="不输出打包进度")
    parser.add_argument("--encoding", default="gbk",
                        help="列出时对乱码文件名使用的编码（默认 gbk）")
    args = parser.parse_args(argv)

    if args.list:
        return do_list(args.zipfile, args.encoding)
    if args.test:
        return do_test(args.zipfile)

    if not args.paths:
        print("请指定要打包的文件或目录", file=sys.stderr)
        return 2

    return do_create(args.zipfile, args.paths, args.quiet)


if __name__ == "__main__":
    sys.exit(main())
