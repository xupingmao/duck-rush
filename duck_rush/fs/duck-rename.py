import xutils
import os
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s|%(levelname)s|%(message)s"
)

DEFAULT_MAX_DEPTH = 5


def encode(dirname="./", max_depth=DEFAULT_MAX_DEPTH, current_depth=0):
    if current_depth > max_depth:
        logging.warning("到达最大递归深度 %s, 跳过目录: %s", max_depth, dirname)
        return
    for fname in os.listdir(dirname):
        new_name = xutils.encode_name(fname)
        old_path = os.path.join(dirname, fname)
        new_path = os.path.join(dirname, new_name)
        is_dir = os.path.isdir(old_path)
        if is_dir and current_depth < max_depth:
            encode(old_path, max_depth, current_depth + 1)
        elif is_dir:
            logging.warning("到达最大递归深度 %s, 跳过目录: %s", max_depth, old_path)
        os.rename(old_path, new_path)


def decode(dirname="./", max_depth=DEFAULT_MAX_DEPTH, current_depth=0):
    if current_depth > max_depth:
        logging.warning("到达最大递归深度 %s, 跳过目录: %s", max_depth, dirname)
        return
    for fname in os.listdir(dirname):
        new_name = xutils.decode_name(fname)
        old_path = os.path.join(dirname, fname)
        new_path = os.path.join(dirname, new_name)
        is_dir = os.path.isdir(old_path)
        if is_dir and current_depth < max_depth:
            decode(old_path, max_depth, current_depth + 1)
        elif is_dir:
            logging.warning("到达最大递归深度 %s, 跳过目录: %s", max_depth, old_path)
        os.rename(old_path, new_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="文件名编解码工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    encode_parser = subparsers.add_parser("encode", help="对文件名进行base64编码")
    encode_parser.add_argument("dirname", nargs="?", default="./", help="目录路径")
    encode_parser.add_argument("-d", "--max-depth", type=int, default=DEFAULT_MAX_DEPTH, help="递归最大深度，默认 %s" % DEFAULT_MAX_DEPTH)

    decode_parser = subparsers.add_parser("decode", help="对文件名进行base64解码")
    decode_parser.add_argument("dirname", nargs="?", default="./", help="目录路径")
    decode_parser.add_argument("-d", "--max-depth", type=int, default=DEFAULT_MAX_DEPTH, help="递归最大深度，默认 %s" % DEFAULT_MAX_DEPTH)

    args = parser.parse_args()
    if args.command == "encode":
        encode(args.dirname, args.max_depth)
    elif args.command == "decode":
        decode(args.dirname, args.max_depth)
    else:
        parser.print_help()