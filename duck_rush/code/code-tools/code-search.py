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
import pdb
from typing import List, Optional, Union, Tuple, Dict, Any

from fnmatch import fnmatch

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
COMMANDS: List[List[Union[callable, List]]] = []
# 5M
FILE_SIZE_LIMIT = 1024 * 1024 * 5

class SearchConfig:
    max_line_width: int = 1000

def set_console_font_color(color: str) -> None:
    if color == "red":
        sys.stdout.write("\033[31m")
    if color == "green":
        sys.stdout.write("\033[32m")
    if color == "orange":
        sys.stdout.write("\033[33m")
    if color == "blue":
        sys.stdout.write("\033[34m")
    if color == "highlight":
        # 黄色背景，白色前景
        sys.stdout.write("\033[43;37m")
    if color == "file_name":
        # 蓝色背景，白色前景
        sys.stdout.write("\033[44;37m")
    if color == "default":
        sys.stdout.write("\033[0m")

class SetTermColor:
    def __init__(self, color: str):
        self.color: str = color

    def __enter__(self) -> 'SetTermColor':
        set_console_font_color(self.color)
        return self

    def __exit__(self, type: Optional[type], value: Optional[Exception], traceback: Optional[Any]) -> None:
        set_console_font_color("default")

class Token:
    pos: List[int] = [-1, -1]
    def __init__(self, type: str = 'symbol', val: Optional[Any] = None, pos: Optional[List[int]] = None):
        self.pos: Optional[List[int]] = pos
        self.type: str = type
        self.val: Optional[Any] = val
    def __str__(self) -> str:
        return f"<Token type={self.type}, val={self.val}, pos={self.pos}>"
    @property
    def line_no(self) -> Optional[int]:
        if self.pos:
            return self.pos[0]
        return None


def findpos(token: Token) -> List[int]:
    if not hasattr(token, 'pos'):
        if hasattr(token, "first"):
            return findpos(token.first)
        print(token)
        return [0,0]
    return token.pos if token.pos else [0,0]


def find_error_line(s: str, pos: List[int]) -> str:
    """
    @param {str} s: source code
    @param {int} pos: position
    """
    #print("****************")
    #print(pos, pos.type, pos.val, pos.pos)
    y = pos[0]
    x = pos[1]
    s = s.replace('\t', ' ')
    line = s.split('\n')[y-1]
    p = ''
    if y < 10: p += ' '
    if y < 100: p += '  '
    r = p + str(y) + ": " + line + "\n"
    r += "     "+" "*x+"^" +'\n'
    return r
    
def compile_error(module_name: str, code: str, token: Optional[Token], e_msg: str = "") -> None:
    if token is not None:
        # print_token(token)
        pos = findpos(token)
        r = find_error_line(code, pos)
        raise Exception('Error at ' + module_name + ':\n' + r + e_msg)
    else:
        raise Exception(e_msg)
    #raise

class BlockComment:
    start = ""
    end = ""

class Tokenizer:

    SYMBOL_CHARS = '-=[];,./!%*()+{}:<>@^#`|&?'
    KEYWORDS = []
    # 从前往后优先匹配
    SYMBOLS = [
        '-=','+=','*=','/=','==','!=','<=','>=',':=',
        '->', # typing return
        '=','-','+','*', '/', '%',
        '<','>',
        '[',']','{','}','(',')','.',':',',',';','#'
    ]

    B_BEGIN = ['[','(','{']
    B_END   = [']',')','}']

    current_position = [-1,-1] # position [line, col]

    def __init__(self, code: str, fpath: str = ""):
        self.fpath = fpath
        self.current_line = 1
        self.line_start_index = 0 # 一行开始的索引
        self.is_newline = True
        self.tokens = [] # type: list[Token]
        self.indent_stack = [0]
        self.brace_count = 0
        self.code = self.clean(code)
        self.current_index = 0
        self.code_length = len(self.code)
        self.is_python = False
        self.ignore_invalid_symbol = False
        
        self.comment_begin = "#"
        self.comment_end = "\n"

        self.cached_lines = []
        self.lines_cached = False
        
        self.block_comment: Optional[BlockComment] = None

    def clean(self, s: str):
        s = s.replace('\r','')
        return s


    def add(self, token_type: str, value: Any): 
        if token_type == 'in':
            last_token = self.tokens.pop()
            if last_token.type == 'not':
                self.tokens.append(Token('notin', value, self.current_position))
            else:
                self.tokens.append(last_token)
                self.tokens.append(Token(token_type, value, self.current_position))
        elif token_type == 'not':
            # is not
            last_token = self.tokens.pop()
            if last_token.type == 'is':
                self.tokens.append(Token("isnot", value, self.current_position))
            else:
                self.tokens.append(last_token)
                self.tokens.append(Token(token_type, value, self.current_position))
        else:
            self.tokens.append(Token(token_type, value, self.current_position))

    def tokenize(self):
        self.current_index = 0
        while self.current_index < self.code_length:
            self._step()

        self.indent(0)

    def _step(self):
        current_char = self.code[self.current_index]
        self.current_position = [self.current_line, self.current_index - self.line_start_index + 1]
        if self.is_python and self.is_newline:
            self.is_newline = False
            self.do_indent()
            return
        
        if current_char == '\n':
            self.do_nl()
            return
        
        if self.code.startswith(self.comment_begin, self.current_index):
            self.do_comment(self.comment_begin, self.comment_end)
            return
        
        if self.block_comment:
            if self.code.startswith(self.block_comment.start, self.current_index):
                self.do_comment(self.block_comment.start, self.block_comment.end)
                return
        
        if current_char in self.SYMBOL_CHARS: 
            self.do_symbol()
            return
        
        if self.is_number_begin(current_char):
            self.do_number()
            return
        
        if self.is_name_begin(current_char):
            self.do_name()
            return
        
        if current_char == '"' or current_char == "'":
            self.do_string()
            return
        
        if current_char == '\\' and self.code[self.current_index+1] == '\n':
            self.current_index += 2
            self.current_line += 1
            self.line_start_index = self.current_index
            return
        
        if self.is_blank(current_char): 
            self.current_index += 1
            return
        
        compile_error('do_tokenize', self.code, Token('', '', self.current_position), f"unknown token at file {self.fpath}")

    def do_indent(self):
        indent_level = 0
        while self.current_index < self.code_length:
            current_char = self.code[self.current_index]
            if current_char != ' ' and current_char != '\t': 
                break
            self.current_index += 1
            indent_level += 1
        # skip blank line or comment line.
        # current_index >= code_length means reaching EOF, which do not need to indent or dedent
        if not self.brace_count and current_char != '\n' and current_char != '#' and self.current_index < self.code_length:
            self.indent(indent_level)

    def indent(self, indent_level: int):
        if indent_level == self.indent_stack[-1]:
            return
        elif indent_level > self.indent_stack[-1]:
            self.indent_stack.append(indent_level)
            self.add('indent', indent_level)
        elif indent_level < self.indent_stack[-1]:
            indent_index = self.indent_stack.index(indent_level)
            while len(self.indent_stack) > indent_index + 1:
                indent_level = self.indent_stack.pop()
                self.add('dedent', indent_level)


    def do_nl(self):
        if not self.brace_count:
            self.add('nl', 'nl')
        self.current_index += 1
        self.is_newline = True
        self.current_line += 1
        self.line_start_index = self.current_index

    
    def do_symbol(self):
        symbol = ""
        for sb in self.SYMBOLS:
            if self.code.startswith(sb, self.current_index):
                self.current_index += len(sb)
                symbol = sb
                break
        if symbol == "":
            if self.ignore_invalid_symbol:
                self.add(self.code[self.current_index], self.code[self.current_index])
                self.current_index += 1
                return
            raise "invalid symbol"
        
        self.add(symbol, symbol)
        if symbol in self.B_BEGIN: 
            self.brace_count += 1
        if symbol in self.B_END: 
            self.brace_count -= 1

    def do_number(self):
        start_index = self.current_index
        self.current_index += 1
        is_float = False
        number_value = ""
        current_char = ""

        while self.current_index < self.code_length:
            current_char = self.code[self.current_index]
            if current_char >= '0' and current_char <= '9': 
                self.current_index += 1
            else:
                break
        
        if current_char == '.':
            is_float = True
            self.current_index += 1
            while self.current_index < self.code_length:
                current_char = self.code[self.current_index]
                if current_char < '0' or current_char > '9': 
                    break
                self.current_index += 1
        number_value = self.code[start_index:self.current_index]
        if is_float:
            self.add('number', float(number_value))
        else:
            self.add('number', int(number_value))

    
    def do_name(self):
        start_index = self.current_index
        self.current_index += 1
        name_value = ""
        while self.current_index < self.code_length:
            if not self.is_name(self.code[self.current_index]):
                break
            self.current_index += 1
        name_value = self.code[start_index:self.current_index]
        if name_value in self.KEYWORDS: 
            self.add(name_value, name_value)
        else: 
            self.add('name', name_value)

    def do_string(self):
        string_value = ''
        quote_char = self.code[self.current_index]  # quote char
        self.current_index += 1
        remaining_length = self.code_length - self.current_index

        if remaining_length >= 5 and self.code[self.current_index] == quote_char and self.code[self.current_index+1] == quote_char:
            # check long string """
            self.current_index += 2
            while self.current_index < self.code_length - 2:
                current_char = self.code[self.current_index]
                if current_char == quote_char and self.code[self.current_index+1] == quote_char and self.code[self.current_index+2] == quote_char:
                    self.current_index += 3
                    self.add('string', string_value)
                    break
                else:
                    string_value += current_char
                    self.current_index += 1
                    if current_char == '\n': 
                        self.current_line += 1
                        self.line_start_index = self.current_index
        else:
            while self.current_index < self.code_length:
                current_char = self.code[self.current_index]
                if current_char == "\\":
                    self.current_index = self.current_index + 1
                    current_char = self.code[self.current_index]
                    if current_char == "n": 
                        current_char = '\n'
                    elif current_char == "r": 
                        current_char = chr(13)
                    elif current_char == "t": 
                        current_char = "\t"
                    elif current_char == "0": 
                        current_char = "\0"
                    elif current_char == 'b': 
                        current_char = '\b'
                    string_value += current_char
                    self.current_index += 1
                elif current_char == quote_char:
                    self.current_index += 1
                    self.add('string', string_value)
                    break
                else:
                    string_value += current_char
                    self.current_index += 1

    def do_comment(self, comment_begin: str = "", comment_end: str = ""):
        self.current_index += len(comment_begin)
        comment_value = ""
        start_index = self.current_index
        while self.current_index < self.code_length:
            """
            原逻辑
            if s[i] == "\n":
                break
            """
            if self.code[self.current_index] == "\n":
                self.current_line += 1
                self.line_start_index = self.current_index + 1
            if self.code.startswith(comment_end, self.current_index):
                break
            self.current_index += 1
        comment_value = self.code[start_index:self.current_index]
        self.current_index += len(comment_end)
        if comment_value.startswith("@debugger"):
            self.add("@", "debugger")

    def is_blank(self, char: str) -> bool:
        return char == ' ' or char == '\t'

    def is_number_begin(self, char: str) -> bool:
        return char >= '0' and char <= '9'
            

    def is_name_begin(self, char: str) -> bool:
        return (char>='a' and char<='z') or (char>='A' and char<='Z') or (char in '_$')
        
    def is_name(self, char: str) -> bool:
        return (char>='a' and char<='z') or (char>='A' and char<='Z') or (char in '_$') or (char>='0' and char<='9')
    
    def get_token(self, index: int = 0) -> Token:
        if index < 0:
            index += len(self.tokens)
        assert index >= 0
        if index < len(self.tokens):
            return self.tokens[index]
        return Token("<EOF>")
    
    def _get_lines(self) -> List[str]:
        if self.lines_cached:
            return self.cached_lines

        self.cached_lines = self.code.split("\n")
        self.lines_cached = True
        return self.cached_lines 

    def __getitem__(self, index: int = 0) -> Token:
        return self.get_token(index)
    
    def get_line_text(self, line_no: int = 1) -> str:
        if line_no < 1:
            return ""
        
        lines = self._get_lines()
        return lines[line_no-1]

class CodeSearcher:
    def __init__(self, file_path: str, search_term: str, ignore_case: bool = False, search_type: str = ""):
        self.file_path: str = file_path
        self.matching_lines: List[Tuple[int, str]] = []
        self.search_term: str = search_term
        self.encoding: Optional[str] = None
        self.ignore_case: bool = ignore_case
        self.search_type: str = search_type
        self.ignore_large_line: bool = True
        self.file_content: Optional[str] = None

    def _get_result(self) -> Optional['CodeSearcher']:
        if len(self.matching_lines) > 0:
            return self
        return None

    def append_match(self, line_number: int, line_text: str) -> None:
        self.matching_lines.append((line_number, line_text))

    def read_file(self, file_path: str) -> str:
        last_error = None
        ENCODING_TUPLE = ("utf-8", "gbk", "mbcs", "latin_1")

        for encoding in ENCODING_TUPLE:
            try:
                with open(file_path, encoding=encoding) as file_pointer:
                    content = file_pointer.read()
                    self.encoding = encoding
                    return content
            except Exception as e:
                last_error = e
        raise Exception(f"can not read file {file_path}", last_error)

    def _do_search_text(self) -> None:
        content = self.read_file(self.file_path)
        self.file_content = content
        search_term = self.search_term
        if self.ignore_case:
            search_term = self.search_term.lower()

        for line_index, line in enumerate(content.split("\n")):
            original_line = line
            if self.ignore_case:
                line = line.lower()
            if self.ignore_large_line and len(line) > SearchConfig.max_line_width:
                continue
            if search_term in line:
                self.append_match(line_index + 1, original_line)

    def print_detail(self) -> None:
        print("\nFile: ", end="")
        # 高亮显示文件名
        with SetTermColor("file_name"):
            print(self.file_path, end="")
        print(" [%s]\n" % len(self.matching_lines))

        for line_number, line in self.matching_lines:
            print("  %04d: " % line_number, end="")
            search_term = self.search_term
            if self.ignore_case:
                search_term = search_term.lower()
                line_lower = line.lower()
                match_position = line_lower.find(search_term)
            else:
                match_position = line.find(search_term)
            
            if match_position != -1:
                # 打印匹配前的部分
                print(line[:match_position], end="")
                # 高亮显示匹配的部分
                with SetTermColor("highlight"):
                    print(line[match_position:match_position+len(search_term)], end="")
                # 打印匹配后的部分
                print(line[match_position+len(search_term):])
            else:
                # 如果没有找到匹配（可能是其他搜索类型），直接打印整行
                print(line)

    def _do_search(self) -> None:
        if self.search_type == "assign":
            return self._search_assign()
        
        return self._do_search_text()
        
    def search(self) -> Optional['CodeSearcher']:
        error = check_file_size(self.file_path)
        if error is not None:
            print("WARN: READ_FILE_FAILED file_path: %s, error: %s" % (self.file_path, error))
            return None
        
        self._do_search()

        return self._get_result()
    
    def _search_assign(self) -> None:
        _, extension = os.path.splitext(self.file_path)
        if extension in (".html", ".txt"):
            return
        
        content = self.read_file(self.file_path)
        self.file_content = content
        search_term = self.search_term
        if self.ignore_case:
            search_term = search_term.lower()
            content = content.lower()

        tokenizer = Tokenizer(content, self.file_path)
        tokenizer.ignore_invalid_symbol = True
        if extension == ".c":
            tokenizer.comment_begin = "/*"
            tokenizer.comment_end = "*/"
        if extension == ".js":
            tokenizer.comment_begin = "//"
            tokenizer.comment_end = "\n"
            tokenizer.block_comment = BlockComment()
            tokenizer.block_comment.start = "/*"
            tokenizer.block_comment.end = "*/"
            
        tokenizer.tokenize()
        current_index = 0
        tokens = tokenizer.tokens
        while current_index < len(tokens):
            token_a = tokens[current_index]
            token_b = tokenizer.get_token(current_index+1)
            if token_a.val == self.search_term and token_b.type in ("=", ":=", ":"):
                line_text = tokenizer.get_line_text(token_a.line_no)
                if line_text:
                    self.append_match(token_a.line_no, line_text)
            current_index += 1


def is_code_file(file_path: str) -> bool:
    _, extension = os.path.splitext(file_path)
    return extension in CODE_EXT_SET


def get_file_size(file_path: str, format: bool = False) -> int:
    file_stat = os.stat(file_path)
    if file_stat and file_stat.st_size >= 0:
        return file_stat.st_size
    return -1

def check_file_size(file_path: str) -> Optional[str]:
    size = get_file_size(file_path)
    if size < 0:
        return "os.stat failed"
    if size > FILE_SIZE_LIMIT:
        return "file too large"
    return None

def read_file(file_path: str) -> str:
    last_error = None
    ENCODING_TUPLE = ("utf-8", "gbk", "mbcs", "latin_1")

    for encoding in ENCODING_TUPLE:
        try:
            with open(file_path, encoding=encoding) as file_pointer:
                content = file_pointer.read()
                return content
        except Exception as e:
            last_error = e
    raise Exception(f"can not read file {file_path}", last_error)

def search_code(search_term: str = "", directory: str = "./", search_type: str = "", ignore_case: bool = True, skip_files: Optional[str] = None, debug: bool = False) -> None:
    if debug:
        print(f"search_term={search_term}, directory={directory}, ignore_case={ignore_case}, skip_files={skip_files}")
    search_results: List[CodeSearcher] = []

    if search_term == "":
        print("=== Duck Code Search 工具 ===")
        print("用于在代码文件中搜索指定的内容")
        print("\n使用方法:")
        print("  python code-search.py --search_term <搜索内容> [选项]")
        print("\n选项:")
        print("  --search_term <内容> 要搜索的内容（必填）")
        print("  --directory <目录>   要搜索的目录，默认为当前目录")
        print("  --search_type <类型> 搜索类型，如 'assign' 表示搜索赋值语句")
        print("  --ignore_case <bool> 是否忽略大小写，默认为 True")
        print("  --skip_files <模式>  跳过匹配的文件，如 '*.pyc'")
        print("  --debug <bool>       是否开启调试模式")
        print("\n示例:")
        print("  # 搜索包含 'def' 的代码")
        print("  python code-search.py --search_term 'def'")
        print("\n  # 在指定目录中搜索")
        print("  python code-search.py --search_term 'class' --directory './src'")
        print("\n  # 搜索赋值语句")
        print("  python code-search.py --search_term 'count' --search_type 'assign'")
        return

    for root, dirs, files in os.walk(directory):
        for file_name in files:
            if skip_files and fnmatch(file_name, skip_files):
                continue

            file_path = os.path.join(root, file_name)
            if not is_code_file(file_path):
                continue
            searcher = CodeSearcher(file_path, search_term, ignore_case=ignore_case, search_type=search_type)
            search_result = searcher.search()
            if search_result is None:
                continue
            search_results.append(search_result)

    for result in search_results:
        result.print_detail()

    if len(search_results) > 0:
        print("\nFind Code in %d files" % len(search_results))
    else:
        print("No file matched")


if __name__ == '__main__':
    fire.Fire(search_code)

