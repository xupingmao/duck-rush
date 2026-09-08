# -*- coding:utf-8 -*-
# @author mark
# @since 2022/03/30 19:12:02
# @modified 2026/09/09 10:00:00
# @filename duck-touch.py
"""创建空文件(不存在时才创建, 已存在的文件不做修改)

用法:
* duck-touch a.txt                  # 创建单个文件
* duck-touch a.txt b.txt c.log      # 一次创建多个文件
"""
import argparse
import os
import sys
from typing import List


def touch(fpath: str) -> bool:
    """创建单个文件; 已存在时直接返回 False, 不做任何修改"""
    if os.path.exists(fpath):
        return False
    with open(fpath, "a+"):
        pass
    return True


def touch_all(files: List[str]) -> int:
    """批量创建文件, 返回失败个数

    单个文件失败(如路径不存在、无权限)时打印错误并继续处理后续文件。
    """
    failed = 0
    for fpath in files:
        try:
            created = touch(fpath)
        except OSError as ex:
            print("创建失败: %s - %s" % (fpath, ex), file=sys.stderr)
            failed += 1
            continue
        if created:
            print("已创建: %s" % fpath)
        else:
            print("已存在(跳过): %s" % fpath)
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="创建空文件, 支持一次传入多个文件名;"
                    "已存在的文件保持原样(不修改内容与时间戳)")
    parser.add_argument("filenames", nargs="+", help="要创建的文件名(可传多个)")
    args = parser.parse_args()

    failed = touch_all(args.filenames)
    if failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
