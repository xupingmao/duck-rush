# encoding=utf-8

import argparse
import sys

def cat_stdin():
    for line in sys.stdin.readlines():
        print(line, end="")
        # sys.stdout.write(line)

def cat_file(filename="", encoding="utf-8"):
    """读取文件内容,用于windows环境模拟cat命令"""
    if filename == "":
        cat_stdin()
        return
    
    with open(filename, encoding=encoding) as fp:
        for line in fp.readlines():
            print(line, end="")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", type=str, default="")
    parser.add_argument("--encoding", type=str, default="utf-8")
    args = parser.parse_args()
    cat_file(args.filename, args.encoding)