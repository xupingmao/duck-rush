# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2022/01/26 20:36:25
# @modified 2022/01/27 11:48:50
# @filename code-count-lines.py

import os
import sys
import argparse
import logging

CODE_TYPE_MAPPING = {
    ".py"   : "Python",
    ".pyx"  : "Cython",

    ".c"    : "C",
    ".h"    : "C-Header",
    ".cpp"  : "CPP",
    ".cc"   : "CPP",
    ".hpp"  : "CPP-Header",
    ".hh"   : "CPP-Header",
    
    ".go"   : "Go",
    ".lua"  : "Lua",
    ".java" : "Java",
    ".sh"   : "Shell",

    ".xml"  : "XML",
    ".html" : "HTML",
    ".xhtml": "XHTML",
    ".yml"  : "YAML",
    
    ".js"   : "JavaScript",
    ".ts"   : "TypeScript",
}

class CodeCounter:

    def __init__(self, dirname, exclude_dirname = None):
        self.dirname = dirname
        self.exclude_dirname = exclude_dirname
        self.lines_dict = dict()
        self.exclude_dirs = set()

    def set_exclude_dirs(self, exclude_dirs):
        if exclude_dirs is None:
            return
        dirs = set()
        for dirname in exclude_dirs:
            dirs.add(os.path.abspath(dirname))

        self.exclude_dirs = dirs

    def get_code_type(self, fpath):
        name, ext = os.path.splitext(fpath)
        return CODE_TYPE_MAPPING.get(ext)

    def need_exclude(self, fpath):
        for dirname in self.exclude_dirs:
            if fpath.startswith(dirname):
                return True
        return False

    def count_lines_no_check(self, code_type, fpath):
        bufsize = 1024 * 4 # 4K
        lines = 0

        with open(fpath, "r", encoding = "utf-8") as fp:
            while True:
                buf = fp.read(bufsize)
                if not buf:
                    break
                lines += buf.count("\n")

        if code_type in self.lines_dict:
            self.lines_dict[code_type] += lines
        else:
            self.lines_dict[code_type] = lines

    def count_lines(self, code_type, fpath):
        try:
            self.count_lines_no_check(code_type, fpath)
        except Exception as e:
            logging.error("process file %r failed", fpath)

    def count(self):
        for root, dirs, files in os.walk(self.dirname):
            for fname in files:
                fpath = os.path.join(root, fname)
                fpath = os.path.abspath(fpath)
                if self.need_exclude(fpath):
                    continue
                
                code_type = self.get_code_type(fpath)
                if code_type is None:
                    continue

                self.count_lines(code_type, fpath)

    def print_info(self):
        print("%-20s%10s" % ("CodeType", "Lines"))
        print("-" * 30)
        total_lines = 0

        for key in sorted(self.lines_dict.keys()):
            line = self.lines_dict[key]
            total_lines += line
            print("%-20s%10s" % (key, line))

        print("-" * 30)
        print("Total lines: %d" % total_lines)


def main():
    parser = argparse.ArgumentParser(description = "代码行统计工具")
    parser.add_argument("dirname", help = "代码文件夹", default = "./", nargs = "?")
    parser.add_argument("--exclude", help = "排除的文件夹", nargs = "*")
    args = parser.parse_args()

    counter = CodeCounter(args.dirname)
    counter.set_exclude_dirs(args.exclude)    
    counter.count()
    counter.print_info()


if __name__ == '__main__':
    main()