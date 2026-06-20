# -*- coding:utf-8 -*-
import sys
import hashlib
import os
import argparse
from io import BufferedReader

CHUNK_SIZE = 8192

ALGORITHMS = sorted(hashlib.algorithms_available)


class HelpFormatter(argparse.RawTextHelpFormatter):
    pass


def get_hash_lib(hash_type: str):
    try:
        return hashlib.new(hash_type)
    except ValueError:
        print("不支持的哈希算法: %s" % hash_type, file=sys.stderr)
        print("可用算法: %s" % ", ".join(ALGORITHMS), file=sys.stderr)
        sys.exit(1)


def calc_checksum(fname: str, checksum_type: str = "sha1"):
    m = get_hash_lib(checksum_type)
    with open(fname, "rb") as fh:
        fh.seek(0)
        while True:
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                break
            m.update(chunk)
    return m.hexdigest()


def format_hash(type: str, hexdigest: str) -> str:
    return "%s: %s" % (type, hexdigest)


def main(path: str, type: str = "sha1", raw: bool = False):
    if os.path.isdir(path):
        for name in os.listdir(path):
            child_path = os.path.join(path, name)
            if os.path.isfile(child_path):
                h = calc_checksum(child_path, type)
                if raw:
                    print(h, child_path)
                else:
                    print(format_hash(type, h), child_path)
    else:
        h = calc_checksum(path, type)
        if raw:
            print(h)
        else:
            print(format_hash(type, h))


if __name__ == "__main__":
    algo_list = ", ".join(ALGORITHMS)
    parser = argparse.ArgumentParser(
        description="计算文件/目录的哈希校验码",
        formatter_class=HelpFormatter,
        epilog="支持的哈希算法 (%d 种):\n  %s" % (len(ALGORITHMS), algo_list),
    )
    parser.add_argument("path", help="文件或目录路径")
    parser.add_argument("--type", default="sha1", choices=ALGORITHMS,
                        help="哈希算法（默认 sha1）")
    parser.add_argument("--raw", action="store_true",
                        help="只输出哈希值，不包含算法前缀")
    args = parser.parse_args()
    main(path=args.path, type=args.type, raw=args.raw)
