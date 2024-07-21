#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/11/12 21:43:07
# @modified 2021/09/30 00:01:05

#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/10/14 00:04:26
# @modified 2020/11/12 15:45:52
import os
import argparse
import sys
import chardet
import fire

CODE_EXT_SET = set([
    ".txt", 
    ".c", ".h", ".cc", ".cpp",
    ".java", 
    ".py", 
    ".html", ".js", ".css",
    ".rb",
    ".sql",
    ".go",
])

# [[func1, args], [func2, args2]]
COMMANDS = []
# 5M
FILE_SIZE_LIMIT = 1024 * 1024 * 5


def set_console_font_color(color):
    if color == "red":
        sys.stdout.write("\033[31m")
    if color == "green":
        sys.stdout.write("\033[32m")
    if color == "orange":
        sys.stdout.write("\033[33m")
    if color == "blue":
        sys.stdout.write("\033[34m")
    if color == "default":
        sys.stdout.write("\033[0m")

class CodeFinder:

    def __init__(self, fpath, source, ignore_case=False):
        self.fpath  = fpath
        self.lines  = []
        self.source = source
        self.encoding = None
        self.ignore_case = ignore_case

    def get_result(self):
        if len(self.lines) > 0:
            return self
        return None

    def append(self, line):
        self.lines.append(line)

    def readfile(self, fpath):
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
        raise Exception(f"can not read file {fpath}", last_err)

    def do_find(self):
        text = self.readfile(self.fpath)
        self.text = text
        source = self.source
        if self.ignore_case:
            source = self.source.lower()

        for index, line in enumerate(text.split("\n")):
            if self.ignore_case:
                line = line.lower()
            if source in line:
                self.lines.append((index,line))

    def print_detail(self):
        # set_console_font_color("blue")
        print("\nFile: %s [%s]\n" % (self.fpath, len(self.lines)))
        # set_console_font_color("default")

        for index, line in self.lines:
            set_console_font_color("red")
            print("  %04d: %s" % (index,line))
            set_console_font_color("default")

def is_code_file(fpath):
    _, ext = os.path.splitext(fpath)
    return ext in CODE_EXT_SET


def get_file_size(fpath, format=False):
    st = os.stat(fpath)
    if st and st.st_size >= 0:
        return st.st_size
    return -1

def check_file_size(fpath):
    size = get_file_size(fpath)
    if size < 0:
        return "os.stat failed"
    if size > FILE_SIZE_LIMIT:
        return "file too large"

def readfile(fpath):
    last_err = None
    ENCODING_TUPLE = ("utf-8", "gbk", "mbcs", "latin_1")

    for encoding in ENCODING_TUPLE:
        try:
            with open(fpath, encoding = encoding) as fp:
                return fp.read()
        except Exception as e:
            last_err = e
    raise Exception(f"can not read file {fpath}", last_err)


def find_in_file(fpath, source, ignore_case=False):
    finder = CodeFinder(fpath, source, ignore_case=ignore_case)

    error = check_file_size(fpath)
    if error != None:
        print("WARN: READ_FILE_FAILED fpath: %s, error: %s" % (fpath, error))
        return

    finder.do_find()
    return finder.get_result()


def code_search(dirname="./", source = "", ignore_case=True):
    results = []

    if source == "":
        print("source不能为空")
        return

    for root, dirs, files in os.walk(dirname):
        for fname in files:
            fpath = os.path.join(root, fname)
            if not is_code_file(fpath):
                continue
            find_result = find_in_file(fpath, source, ignore_case=ignore_case)
            if find_result is None:
                continue
            results.append(find_result)

    for result in results:
        result.print_detail()

    if len(results) > 0:
        print("\nFind Code in %d files" % len(results))
    else:
        print("No file matched")


if __name__ == '__main__':
    fire.Fire(code_search)

