# encoding=utf-8

import fire
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
    fire.Fire(cat_file)