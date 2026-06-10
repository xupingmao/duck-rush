import xutils
import os
import argparse


def encode(dirname="./"):
    for fname in os.listdir(dirname):
        new_name = xutils.encode_name(fname)
        old_path = os.path.join(dirname, fname)
        new_path = os.path.join(dirname, new_name)
        os.rename(old_path, new_path)


def decode(dirname="./"):
    for fname in os.listdir(dirname):
        new_name = xutils.decode_name(fname)
        old_path = os.path.join(dirname, fname)
        new_path = os.path.join(dirname, new_name)
        os.rename(old_path, new_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="文件名编解码工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    encode_parser = subparsers.add_parser("encode", help="对文件名进行base64编码")
    encode_parser.add_argument("dirname", nargs="?", default="./", help="目录路径")

    decode_parser = subparsers.add_parser("decode", help="对文件名进行base64解码")
    decode_parser.add_argument("dirname", nargs="?", default="./", help="目录路径")

    args = parser.parse_args()
    if args.command == "encode":
        encode(args.dirname)
    elif args.command == "decode":
        decode(args.dirname)
    else:
        parser.print_help()