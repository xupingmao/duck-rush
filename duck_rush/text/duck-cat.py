# encoding=utf-8

import argparse
import sys

def cat_lines(lines, number=False):
    for index, line in enumerate(lines, 1):
        if number:
            print("%6d\t%s" % (index, line), end="")
        else:
            print(line, end="")

def cat_stdin(number=False):
    cat_lines(sys.stdin.readlines(), number)

def cat_file(filename="", encoding="utf-8", number=False):
    """读取文件内容,用于windows环境模拟cat命令"""
    if filename == "":
        cat_stdin(number)
        return
    
    with open(filename, encoding=encoding) as fp:
        cat_lines(fp.readlines(), number)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", type=str, nargs="?", default="")
    parser.add_argument("--encoding", type=str, default="utf-8")
    parser.add_argument("-n", "--number", action="store_true",
                        help="对输出的所有行加上行号(类似 cat -n)")
    args = parser.parse_args()
    cat_file(args.filename, args.encoding, args.number)