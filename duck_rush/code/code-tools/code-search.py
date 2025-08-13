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

class SetTermColor:
    def __init__(self, color: str):
        self.color = color

    def __enter__(self):
        set_console_font_color(self.color)
        return self

    def __exit__(self, type, value, traceback):
        set_console_font_color("default")

class Token:
    pos = [-1, -1]
    def __init__(self, type='symbol', val=None, pos=None):
        self.pos  = pos
        self.type = type
        self.val  = val
    def __str__(self):
        return f"<Token type={self.type}, val={self.val}, pos={self.pos}>"
    @property
    def line_no(self):
        return self.pos[0]


def findpos(token: Token):
    if not hasattr(token, 'pos'):
        if hasattr(token, "first"):
            return findpos(token.first)
        print(token)
        return [0,0]
    return token.pos


def find_error_line(s: str, pos: "list[int]"):
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
    
def compile_error(module_name: str, code:str, token, e_msg = ""):
    if token != None:
        # print_token(token)
        pos = findpos(token)
        r = find_error_line(code, pos)
        raise Exception('Error at ' + module_name + ':\n' + r + e_msg)
    else:
        raise Exception(e_msg)
    #raise


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

    pos = [-1,-1] # position [line, col]

    def __init__(self, code:str):
        self.line=1
        self.line_start=0 # 一行开始的索引
        self.nl=True
        self.result=[] # type: list[Token]
        self.indent_stack = [0]
        self.braces=0
        self.code = self.clean(code)
        self.is_python = False
        self.ignore_invalid_symbol = False
        self.comment_begin = "#"
        self.comment_end = "\n"

        self._lines = []
        self._cache_lines = False

    def clean(self, s: str):
        s = s.replace('\r','')
        return s


    def add(self,t,v): 
        if t == 'in':
            last = self.result.pop()
            if last.type == 'not':
                self.result.append(Token('notin', v, self.pos))
            else:
                self.result.append(last)
                self.result.append(Token(t,v,self.pos))
        elif t == 'not':
            # is not
            last = self.result.pop()
            if last.type == 'is':
                self.result.append(Token("isnot", v, self.pos))
            else:
                self.result.append(last)
                self.result.append(Token(t,v,self.pos))
        else:
            self.result.append(Token(t,v,self.pos))

    def tokenize(self):
        i = 0
        code = self.code
        l = len(self.code)
        while i < l:
            c = code[i]
            self.pos = [self.line,i-self.line_start+1]
            if self.is_python and self.nl:
                self.nl = False
                i = self.do_indent(code,i,l)
            elif c == '\n':
                i = self.do_nl(code,i,l)
            elif code.startswith(self.comment_begin, i):
                i = self.do_comment(code,i,l)
            elif c in self.SYMBOL_CHARS: 
                i = self.do_symbol(code,i,l)
            elif self.is_number_begin(c):
                i = self.do_number(code,i,l)
            elif self.is_name_begin(c):
                i = self.do_name(code,i,l)
            elif c == '"' or c == "'":
                i = self.do_string(code,i,l)
            elif c == '\\' and code[i+1] == '\n':
                i += 2; 
                self.line+=1; 
                self.line_start = i
            elif self.is_blank(c): 
                i += 1
            else:
                compile_error('do_tokenize',code, Token('', '', self.pos), "unknown token")
        self.indent(0)


    def do_indent(self,s,i,l):
        v = 0
        while i<l:
            c = s[i]
            if c != ' ' and c != '\t': 
                break
            i+=1
            v+=1
        # skip blank line or comment line.
        # i >= l means reaching EOF, which do not need to indent or dedent
        if not self.braces and c != '\n' and c != '#' and i < l:
            self.indent(v)
        return i

    def indent(self, v: int):
        if v == self.indent_stack[-1]:
            return
        elif v > self.indent_stack[-1]:
            self.indent_stack.append(v)
            self.add('indent',v)
        elif v < self.indent_stack[-1]:
            n = self.indent_stack.index(v)
            while len(self.indent_stack) > n+1:
                v = self.indent_stack.pop()
                self.add('dedent',v)


    def do_nl(self, s,i,l):
        if not self.braces:
            self.add('nl','nl')
        i+=1
        self.nl=True
        self.line+=1
        self.line_start=i
        return i

    
    def do_symbol(self, s:str, i:int, l:int):
        v = ""
        for sb in self.SYMBOLS:
            if s.startswith(sb, i):
                i += len(sb)
                v = sb
                break
        if v == "":
            if self.ignore_invalid_symbol:
                self.add(s[i], s[i])
                i += 1
                return i
            raise "invalid symbol"
        
        self.add(v,v)
        if v in self.B_BEGIN: 
            self.braces += 1
        if v in self.B_END: 
            self.braces -= 1
        return i

    def do_number(self, s:str,i:int,l:int):
        start = i
        i+=1
        is_float = False
        value = ""
        c = ""

        while i<l:
            c = s[i]
            if c >= '0' and c <= '9': 
                i += 1
            else:
                break
        
        if c == '.':
            is_float = True
            i+=1
            while i<l:
                c = s[i]
                if c < '0' or c > '9': 
                    break
                i+=1
        value = s[start:i]
        if is_float:
            self.add('number',float(value))
        else:
            self.add('number',int(value))
        return i

    
    def do_name(self,text:str,i:int,l:int):
        start = i
        i+=1
        value = ""
        while i<l:
            if not self.is_name(text[i]):
                break
            i+=1
        value = text[start:i]
        if value in self.KEYWORDS: 
            self.add(value, value)
        else: 
            self.add('name',value)
        return i

    def do_string(self, s:str,i:int,l:int):
        v = ''
        q = s[i]  # quote char
        i += 1
        rest = l - i

        if rest >= 5 and s[i] == q and s[i+1] == q:
            # check long string """
            i += 2
            while i<l-2:
                c = s[i]
                if c == q and s[i+1] == q and s[i+2] == q:
                    i += 3
                    self.add('string',v)
                    break
                else:
                    v+=c; i+=1
                    if c == '\n': 
                        self.line += 1
                        self.line_start = i
        else:
            while i<l:
                c = s[i]
                if c == "\\":
                    i = i+1; c = s[i]
                    if c == "n": c = '\n'
                    elif c == "r": c = chr(13)
                    elif c == "t": c = "\t"
                    elif c == "0": c = "\0"
                    elif c == 'b': c = '\b'
                    v+=c;i+=1
                elif c == q:
                    i += 1
                    self.add('string',v)
                    break
                else:
                    v+=c;i+=1
        return i

    def do_comment(self, text:str,i:int,l:int):
        i += len(self.comment_begin)
        value = ""
        start = i
        while i<l:
            """
            原逻辑
            if s[i] == "\n":
                break
            """
            if text[i] == "\n":
                self.line += 1
                self.line_start = i+1
            if text.startswith(self.comment_end, i):
                break
            i += 1
        value = text[start:i]
        i += len(self.comment_end)
        if value.startswith("@debugger"):
            self.add("@", "debugger")
        return i

    def is_blank(self, c):
        return c == ' ' or c == '\t'

    def is_number_begin(self, c):
        return c >= '0' and c <= '9'
            

    def is_name_begin(self, c):
        return (c>='a' and c<='z') or (c>='A' and c<='Z') or (c in '_$')
        
    def is_name(self, c):
        return (c>='a' and c<='z') or (c>='A' and c<='Z') or (c in '_$') or (c>='0' and c<='9')
    
    def get_token(self, index = 0):
        if index < 0:
            index += len(self.result)
        assert index >= 0
        if index < len(self.result):
            return self.result[index]
        return Token("<EOF>")
    
    def _get_lines(self):
        if self._cache_lines:
            return self._lines

        self._lines = self.code.split("\n")
        self._cache_lines = True
        return self._lines 

    def __getitem__(self, index = 0):
        return self.get_token(index)
    
    def get_line_text(self, line_no = 1):
        if line_no < 1:
            return ""
        
        lines = self._get_lines()
        return lines[line_no-1]

class CodeSearcher:
    def __init__(self, fpath: str, source: str, ignore_case=False, search_type = ""):
        self.fpath  = fpath
        self.lines  = []
        self.source = source
        self.encoding = None
        self.ignore_case = ignore_case
        self.search_type = search_type

    def _get_result(self):
        if len(self.lines) > 0:
            return self
        return None

    def append(self, line_no: int, line_text: str):
        self.lines.append((line_no, line_text))

    def readfile(self, fpath:str):
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

    def _do_search_text(self):
        text = self.readfile(self.fpath)
        self.text = text
        source = self.source
        if self.ignore_case:
            source = self.source.lower()

        for index, line in enumerate(text.split("\n")):
            original_line = line
            if self.ignore_case:
                line = line.lower()
            if source in line:
                self.append(index + 1, original_line)

    def print_detail(self):
        print("\nFile: %s [%s]\n" % (self.fpath, len(self.lines)))

        for index, line in self.lines:
            with SetTermColor("red"):
                print("  %04d: %s" % (index,line))

    def _do_search(self):
        if self.search_type == "assign":
            return self._search_assign()
        
        return self._do_search_text()
        
    def search(self):
        error = check_file_size(self.fpath)
        if error != None:
            print("WARN: READ_FILE_FAILED fpath: %s, error: %s" % (self.fpath, error))
            return
        
        self._do_search()

        return self._get_result()
    
    def _search_assign(self):
        _, ext = os.path.splitext(self.fpath)
        if ext in (".html", ".txt"):
            return
        
        text = self.readfile(self.fpath)
        self.text = text
        source = self.source
        if self.ignore_case:
            source = source.lower()
            text = text.lower()

        tokenizer = Tokenizer(text)
        tokenizer.ignore_invalid_symbol = True
        if ext == ".c":
            tokenizer.comment_begin = "/*"
            tokenizer.comment_end = "*/"
        tokenizer.tokenize()
        index = 0
        while index < len(tokenizer.result):
            a = tokenizer[index]
            b = tokenizer[index+1]
            if a.val == self.source and b.type in ("=", ":=", ":"):
                line_text = tokenizer.get_line_text(a.line_no)
                self.append(a.line_no, line_text)
            index += 1


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

def search_code(source = "", dirname="./", search_type = "", ignore_case=True, skip_files = None, debug = False):
    if debug:
        print(f"source={source}, dirname={dirname}, ignore_case={ignore_case}, skip_files={skip_files}")
    results = [] # type: list[CodeSearcher]

    if source == "":
        print("source不能为空")
        return

    for root, dirs, files in os.walk(dirname):
        for fname in files:
            if skip_files and fnmatch(fname, skip_files):
                continue

            fpath = os.path.join(root, fname)
            if not is_code_file(fpath):
                continue
            searcher = CodeSearcher(fpath, source, ignore_case=ignore_case, search_type = search_type)
            find_result = searcher.search()
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
    fire.Fire(search_code)

