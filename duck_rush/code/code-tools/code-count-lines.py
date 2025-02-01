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

class CommentType:
    HASH = 1 # `#`号注释比如python
    DOUBLE_SLASH = 2 # // 双斜线风格
    SLASH_BLOCK  = 3 # /**/ C语言风格注释
    DOUBLE_MINUS = 4 # -- 双减号风格， sql/lua等

class CodeTypeEnumItem:
    def __init__(self, name="", ext_list=[], comment_type=0):
        self.name = name
        self.ext_list = ext_list
        self.comment_type = comment_type

class CodeTypeEnum:
    python = CodeTypeEnumItem("Python", [".py"], comment_type=CommentType.HASH)
    cython = CodeTypeEnumItem("Cython", [".pyx"], comment_type=CommentType.HASH)
    c = CodeTypeEnumItem("C", [".c"], comment_type=CommentType.SLASH_BLOCK)
    c_header = CodeTypeEnumItem("C-Header", [".h"], comment_type=CommentType.SLASH_BLOCK)
    cpp = CodeTypeEnumItem("CPP", [".cpp", ".cxx", ".cc"], comment_type=CommentType.DOUBLE_SLASH)
    cpp_header = CodeTypeEnumItem("CPP-Header", [".hpp", ".hh"], comment_type=CommentType.DOUBLE_SLASH)
    go = CodeTypeEnumItem("Go", [".go"], comment_type=CommentType.DOUBLE_SLASH)
    lua = CodeTypeEnumItem("Lua", [".lua"], comment_type=CommentType.DOUBLE_MINUS)
    java = CodeTypeEnumItem("Java", [".java"], comment_type=CommentType.DOUBLE_SLASH)
    shell = CodeTypeEnumItem("Shell", [".sh"], comment_type=CommentType.HASH)
    xml = CodeTypeEnumItem("XML", [".xml"])
    html = CodeTypeEnumItem("HTML", [".html"])
    xhtml = CodeTypeEnumItem("XHTML", [".xhtml"])
    yaml = CodeTypeEnumItem("YAML", [".yml"], comment_type=CommentType.HASH)
    javascript = CodeTypeEnumItem("JavaScript", [".js"], comment_type=CommentType.DOUBLE_SLASH)
    typescript = CodeTypeEnumItem("TypeScript", [".ts"], comment_type=CommentType.DOUBLE_SLASH)
    php = CodeTypeEnumItem("PHP", [".php"], comment_type=CommentType.DOUBLE_SLASH)
    sql = CodeTypeEnumItem("SQL", [".sql"], comment_type=CommentType.DOUBLE_MINUS)
    css = CodeTypeEnumItem("CSS", [".css"], comment_type=CommentType.SLASH_BLOCK)

    @classmethod
    def init(cls):
        ext_to_name_dict = {}
        code_type_dict = {} # type: dict[str, CodeTypeEnumItem]
        for key in cls.__dict__:
            value = getattr(cls, key, None)
            if isinstance(value, CodeTypeEnumItem):
                code_type_dict[value.name] = value
                for ext in value.ext_list:
                    ext_to_name_dict[ext] = value.name
        
        cls.code_type_dict = code_type_dict
        cls.ext_to_name_dict = ext_to_name_dict

    @classmethod
    def get_code_type_name_by_ext(cls, ext=""):
        return cls.ext_to_name_dict.get(ext)
    
    @classmethod
    def get_check_func(cls, code_type):
        """快速检测注释,不是基于语义的,可能不准确"""
        type_info = cls.code_type_dict.get(code_type)
        if type_info is None:
            return None
        
        if type_info.comment_type == CommentType.HASH:
            return cls.is_hash_comment
        if type_info.comment_type == CommentType.DOUBLE_SLASH:
            return cls.is_double_slash_comment
        if type_info.comment_type == CommentType.DOUBLE_MINUS:
            return cls.is_double_minus_comment
        if type_info.comment_type == CommentType.SLASH_BLOCK:
            return cls.is_slash_block_comment

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
    
    @staticmethod
    def is_slash_block_comment(line: str):
        """支持下列模式
        /* 单行注释 */

        /* 多行注释
        ** 第2行注释
        ** 第3行注释
        */

        int i = 0; /* 这种先算到代码,不统计到注释 */
        """
        line = line.strip()
        if line.startswith("/*") and line.endswith("*/"):
            return True
        if line.startswith("**"):
            return True
        return line.startswith("/*")

CodeTypeEnum.init()

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

    def __init__(self, dirname_list, exclude_dirname = None, debug=False):
        if debug:
            print(f"dirname_list:{dirname_list}, exclude_dirname:{exclude_dirname}")
        self.dirname_list = dirname_list
        self.exclude_dirname = exclude_dirname
        self.blank_lines_dict = dict()
        self.code_lines_dict = dict() # dict[code_type, code_lines]
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
        return CodeTypeEnum.get_code_type_name_by_ext(ext)

    def need_exclude(self, fpath: str):
        for dirname in self.exclude_dirs:
            if fpath.startswith(dirname) or fnmatch.fnmatch(fpath, dirname):
                return True
        return False

    def count_lines_no_check(self, code_type, fpath):
        bufsize = 1024 * 4 # 4K
        blank_lines = 0
        comment_lines = 0
        code_lines = 0
        is_comment_func = CodeTypeEnum.get_check_func(code_type)

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
                        code_lines += 1

        if code_type not in self.code_lines_dict:
            self.blank_lines_dict[code_type] = 0
            self.files_dict[code_type] = 0
            self.comment_dict[code_type] = 0
            self.code_lines_dict[code_type] = 0
        
        self.blank_lines_dict[code_type] += blank_lines
        self.files_dict[code_type] += 1
        self.comment_dict[code_type] += comment_lines
        self.code_lines_dict[code_type] += code_lines

    def count_lines(self, code_type, fpath):
        try:
            self.count_lines_no_check(code_type, fpath)
        except Exception as e:
            logging.error(f"process file {fpath} failed, err: {e}")

    def count(self):
        for dirname in self.dirname_list:
            for root, dirs, files in os.walk(dirname):
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
        pt = MyPrinter(["Language".ljust(20), "files", "blank".ljust(10), "comment".ljust(10), "code".rjust(10)])
        pt.print_line_sep()
        pt.print_headings()
        total_codes = 0
        total_files = 0
        total_comments = 0
        total_blanks = 0

        for key in sorted(self.code_lines_dict.keys()):
            code_lines = self.code_lines_dict[key]
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
    parser.add_argument("dirname", help = "代码文件夹", default = ["./"], nargs = "*")
    parser.add_argument("--exclude", help = "排除的文件夹", nargs = "*")
    parser.add_argument("--debug", help="是否开启调试", default=False, action="store_true")
    args = parser.parse_args()

    counter = CodeCounter(args.dirname, debug=args.debug)
    counter.set_exclude_dirs(args.exclude)    
    counter.count()
    counter.print_info()


if __name__ == '__main__':
    main()