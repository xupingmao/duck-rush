# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/10/14 00:04:26
# @modified 2021/09/29 23:50:33

import os
import argparse
import sys
import chardet
from typing import List, Optional, Union, Tuple, TextIO

duck_rush_dir = os.environ.get("DUCK_RUSH_DIR", "")
if duck_rush_dir not in sys.path:
    sys.path.append(duck_rush_dir)

from duck_rush.utils.os_util import set_console_font_color

CODE_EXT_SET = set([
    ".txt", 
    ".c", ".h", ".cc", ".cpp",
    ".java", 
    ".py", 
    ".html", ".js", ".css",
    ".rb",
    ".sql"
])

# [[func1, args], [func2, args2]]
COMMANDS: List[List[Union[callable, List]]] = []
# 5M
FILE_SIZE_LIMIT = 1024 * 1024 * 5

class Message:
    CONFIRM_REPLACE: str = "Replace Code?(Y/N):"
    FIND_RESULT: str = "\nFind Code in %d files"

MESSAGE = Message()
def init_language() -> None:
    global MESSAGE
    MESSAGE.CONFIRM_REPLACE = "是否确认替换?(Y/N):"
    MESSAGE.FIND_RESULT = "\n在%d个文件中找到目标代码"


class CodeFinder:

    def __init__(self, fpath: str, source: str, target: str):
        self.fpath: str = fpath
        self.lines: List[str] = []
        self.source: str = source
        self.target: str = target
        self.encoding: Optional[str] = None
        self.text: Optional[str] = None

    def get_result(self) -> Optional['CodeFinder']:
        if len(self.lines) > 0:
            return self
        return None

    def append(self, line: str) -> None:
        self.lines.append(line)

    def ask(self) -> None:
        print("\nFile: %s" % self.fpath)
        for line in self.lines:
            print("")
            set_console_font_color("red")
            print("--- %s" % line)

            set_console_font_color("green")
            new_line = line.replace(self.source, self.target)
            print("+++ %s" % new_line)

            set_console_font_color("default")

    def readfile(self, fpath: str, raise_error: bool = True) -> str:
        last_err = None
        ENCODING_TUPLE = ("utf-8", "gbk", "mbcs", "latin_1")

        for encoding in ENCODING_TUPLE:
            try:
                with open(fpath, encoding = encoding) as fp:
                    text = fp.read()
                    self.encoding = encoding
                    return text
            except Exception as e:
                last_err = e
        if raise_error:
            raise Exception("can not read file %s" % fpath, last_err)
        return ""

    def do_find(self) -> None:
        text = self.readfile(self.fpath)
        self.text = text

        for line in text.split("\n"):
            if self.source in line:
                self.lines.append(line)

    def do_replace(self) -> None:
        # 1. backup
        if self.text is not None:
            new_text = self.text.replace(self.source, self.target)
            with open(self.fpath, encoding = self.encoding, mode = "w+") as fp:
                fp.write(new_text)

def is_code_file(fpath: str) -> bool:
    _, ext = os.path.splitext(fpath)
    return ext in CODE_EXT_SET


def get_file_size(fpath: str, format: bool = False) -> int:
    st = os.stat(fpath)
    if st and st.st_size >= 0:
        return st.st_size
    return -1

def check_file_size(fpath: str) -> Optional[str]:
    size = get_file_size(fpath)
    if size < 0:
        return "os.stat failed"
    if size > FILE_SIZE_LIMIT:
        return "file too large"
    return None

def readfile(fpath: str, raise_error: bool = True) -> str:
    last_err = None
    ENCODING_TUPLE = ("utf-8", "gbk", "mbcs", "latin_1")

    for encoding in ENCODING_TUPLE:
        try:
            with open(fpath, encoding = encoding) as fp:
                return fp.read()
        except Exception as e:
            last_err = e
    if raise_error:
        raise Exception("can not read file %s" % fpath, last_err)
    return ""


def find_in_file(fpath: str, source: str, target: str) -> Optional[CodeFinder]:
    finder = CodeFinder(fpath, source, target)

    error = check_file_size(fpath)
    if error is not None:
        print("WARN: READ_FILE_FAILED fpath: %s, error: %s" % (fpath, error))
        return None

    finder.do_find()
    return finder.get_result()


def replace_dir(dirname: str = "./", source: Optional[str] = None, target: Optional[str] = None) -> None:
    results: List[CodeFinder] = []

    for root, dirs, files in os.walk(dirname):
        for fname in files:
            fpath = os.path.join(root, fname)
            if not is_code_file(fpath):
                continue
            if source is None or target is None:
                continue
            find_result = find_in_file(fpath, source, target)
            if find_result is None:
                continue
            results.append(find_result)

    for result in results:
        result.ask()

    if len(results) > 0:
        print(MESSAGE.FIND_RESULT % len(results))
    else:
        print("No file matched")
        return

    print("")
    check = input(MESSAGE.CONFIRM_REPLACE)
    if check.lower() == "y":
        for result in results:
            result.do_replace()


def main() -> None:
    init_language()
    parser = argparse.ArgumentParser(description = "代码替换工具")
    parser.add_argument("source", help = "旧的字符串")
    parser.add_argument("target", help = "新的字符串")

    args = parser.parse_args()
    dirname = "./"
    replace_dir(dirname, source = args.source, target = args.target)

if __name__ == '__main__':
    main()
