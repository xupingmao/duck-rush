# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2022/01/26 20:36:25
# @modified 2022/01/27 11:48:50
# @filename code-count-lines.py

import os
import sys
import argparse
import logging
import fnmatch
import typing

class CodeType:
    python = "Python"
    cython = "Cython"
    c = "C"
    c_header = "C-Header"
    cpp = "CPP"
    cpp_header = "CPP-Header"
    go = "Go"
    lua = "Lua"
    java = "Java"
    shell = "Shell"
    xml = "XML"
    html = "HTML"
    xhtml = "XHTML"
    yaml = "YAML"
    javascript = "JavaScript"
    typescript = "TypeScript"
    php = "PHP"
    sql = "SQL"
    
    @classmethod
    def get_check_func(cls, code_type):
        """快速检测评论,不是基于语义的,可能不准确"""
        if code_type in (cls.python, cls.shell, cls.yaml):
            return CodeType.is_hash_comment
        if code_type in (cls.java, cls.php, cls.javascript, cls.typescript, cls.go):
            return CodeType.is_double_slash_comment
        if code_type in (CodeType.lua, CodeType.sql):
            return CodeType.is_double_minus_comment
        return None
    
    @staticmethod
    def is_hash_comment(line: str):
        return line.startswith("#")
    
    @staticmethod
    def is_double_slash_comment(stripped_line: str):
        return stripped_line.startswith("//")
    
    @staticmethod
    def is_double_minus_comment(line: str):
        return line.startswith("--")

CODE_TYPE_MAPPING = {
    ".py"   : CodeType.python,
    ".pyx"  : CodeType.cython,

    ".c"    : CodeType.c,
    ".h"    : CodeType.c_header,
    ".cpp"  : CodeType.cpp,
    ".cc"   : CodeType.cpp,
    ".hpp"  : CodeType.cpp_header,
    ".hh"   : CodeType.cpp_header,
    
    ".go"   : CodeType.go,
    ".lua"  : CodeType.lua,
    ".java" : CodeType.java,
    ".sh"   : CodeType.shell,

    ".xml"  : CodeType.xml,
    ".html" : CodeType.html,
    ".xhtml": CodeType.xhtml,
    ".yml"  : CodeType.yaml,
    
    ".js"   : CodeType.javascript,
    ".ts"   : CodeType.typescript,

    ".php": CodeType.php,
    ".sql": CodeType.sql,
}

class MyPrinter:
    
    def __init__(self, headings: typing.List[str]):
        self.headings = headings
        self.blank_sep = " " * 5
        self.line_sep = "-"

    def print_headings(self):
        separators = []
        for heading in self.headings:
            separators.append(self.line_sep * len(heading))
        
        print(self.blank_sep.join(self.headings))
        self.print_line_sep()

    def print_line(self, *args):
        items = []
        for index, heading in enumerate(self.headings):
            value = args[index]
            length = len(heading)
            if index == len(self.headings) - 1:
                items.append(str(value).rjust(length))
            else:
                items.append(str(value).ljust(length))
        print(self.blank_sep.join(items))

    def print_line_sep(self):
        char_count = len(self.blank_sep.join(self.headings))
        print(self.line_sep*char_count)

class CodeCounter:

    def __init__(self, dirname, exclude_dirname = None):
        self.dirname = dirname
        self.exclude_dirname = exclude_dirname
        self.lines_dict = dict()
        self.blank_lines_dict = dict()
        self.files_dict = dict()
        self.comment_dict = dict()
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

    def need_exclude(self, fpath: str):
        for dirname in self.exclude_dirs:
            if fpath.startswith(dirname) or fnmatch.fnmatch(fpath, dirname):
                return True
        return False

    def count_lines_no_check(self, code_type, fpath):
        bufsize = 1024 * 4 # 4K
        lines = 0
        blank_lines = 0
        comment_lines = 0
        is_comment_func = CodeType.get_check_func(code_type)

        with open(fpath, "r", encoding = "utf-8", errors="ignore") as fp:
            while True:
                buf = fp.read(bufsize)
                if not buf:
                    break
                text_lines = buf.split("\n")

                for line in text_lines:
                    line_strip = line.strip()
                    if line_strip == "":
                        blank_lines += 1
                    elif is_comment_func != None and is_comment_func(line_strip):
                        comment_lines += 1
                    else:
                        lines += 1

        if code_type not in self.lines_dict:
            self.lines_dict[code_type] = 0
            self.blank_lines_dict[code_type] = 0
            self.files_dict[code_type] = 0
            self.comment_dict[code_type] = 0
        
        self.lines_dict[code_type] += lines
        self.blank_lines_dict[code_type] += blank_lines
        self.files_dict[code_type] += 1
        self.comment_dict[code_type] += comment_lines

    def count_lines(self, code_type, fpath):
        try:
            self.count_lines_no_check(code_type, fpath)
        except Exception as e:
            logging.error(f"process file {fpath} failed, err: {e}")

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
        pt = MyPrinter(["Language".ljust(20), "files", "blank", "comment", "code".rjust(10)])
        pt.print_line_sep()
        pt.print_headings()
        total_codes = 0
        total_files = 0
        total_comments = 0
        total_blanks = 0

        for key in sorted(self.lines_dict.keys()):
            code_lines = self.lines_dict[key]
            blank_lines = self.blank_lines_dict.get(key, 0)
            comment_lines = self.comment_dict.get(key, 0)
            files = self.files_dict.get(key, 0)

            total_codes += code_lines
            total_files += files
            total_comments += comment_lines
            total_blanks += blank_lines

            pt.print_line(key, files, blank_lines, comment_lines, code_lines)

        pt.print_line_sep()
        pt.print_line("SUM", total_files, total_blanks, total_comments, total_codes)
        pt.print_line_sep()


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