# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/09/06
# @filename duck-list-symbol.py
# @description 列出代码中的符号(类/函数/方法/属性/变量/参数), Python 用 AST 精确
#              提取, 其他语言用正则回退(函数/类); 以扁平列表输出, 支持按类型过滤

import sys
import io
import os
import re
import ast
import argparse
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple, Iterator

# ============================== 通用工具 ==============================

# 目录递归时跳过的目录名(避免扫描依赖/构建产物等造成卡顿)
IGNORE_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".tox",
    "dist", "build", ".idea", ".vscode", "site-packages", ".mypy_cache",
})

# 文件扩展名 -> 语言
EXT_TO_LANG: Dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".lua": "lua",
    ".c": "cfamily",
    ".h": "cfamily",
    ".cpp": "cfamily",
    ".cc": "cfamily",
    ".cxx": "cfamily",
    ".hpp": "cfamily",
    ".cs": "cfamily",
    ".java": "cfamily",
    ".swift": "cfamily",
    ".kt": "cfamily",
    ".m": "cfamily",
}

# 无法仅靠扩展名判断时, 用 shebang 推断
SHEBANG_TO_LANG: Dict[str, str] = {
    "python": "python",
    "python3": "python",
    "sh": "shell",
    "bash": "shell",
    "zsh": "shell",
    "node": "javascript",
    "lua": "lua",
    "ruby": "ruby",
    "php": "php",
}

# 使用缩进而非花括号界定作用域的语言
INDENT_LANGS = ("python", "ruby")

# 支持的符号类型
KINDS = ("class", "function", "method", "attribute", "variable", "param", "import")


def ensure_utf8_output() -> None:
    """强制以 UTF-8 输出, 避免 Windows 控制台代码页导致中文乱码"""
    out = sys.stdout
    reconf = getattr(out, "reconfigure", None)
    if callable(reconf):
        try:
            reconf(encoding="utf-8")
            return
        except (AttributeError, ValueError):
            pass
    buf = getattr(out, "buffer", None)
    if buf is not None:
        sys.stdout = io.TextIOWrapper(buf, encoding="utf-8", errors="replace")


def iter_lines(stream, encoding: str) -> Iterator[Tuple[int, str]]:
    """从二进制流逐行解码, 返回 (行号, 去尾部换行的内容)"""
    for line_no, raw in enumerate(stream, 1):
        yield line_no, raw.decode(encoding, errors="replace").rstrip("\n")


def walk_dir(root: str) -> List[str]:
    """递归遍历目录, 仅返回扩展名可识别语言(EXT_TO_LANG)的文件, 跳过 IGNORE_DIRS."""
    result: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in EXT_TO_LANG:
                result.append(os.path.join(dirpath, fn))
    return result


# 单行字符数超过该阈值即视为疑似压缩/打包代码
MINIFIED_LINE_LEN = 10000


def is_likely_minified(lines: List[Tuple[int, str]]) -> bool:
    """判断是否为压缩过的代码: 存在超长单行, 或行数极少却整体极密."""
    if not lines:
        return False
    max_len = max(len(text) for _, text in lines)
    if max_len > MINIFIED_LINE_LEN:
        return True
    if len(lines) <= 3 and max_len > 2000:
        return True
    return False


# ============================== 符号数据结构 ==============================

@dataclass
class Symbol:
    kind: str          # class / function / method / attribute / variable / param / import
    name: str          # 含所属作用域前缀, 如 "MyClass.do_x"
    line: int          # 定义所在行号(1-based)
    file: str          # 文件标签(通常为路径, 单文件时可能为空串)


# ============================== Python AST 提取 ==============================

def _assign_names(node: ast.stmt) -> List[str]:
    """提取赋值语句中简单名称(排除 self.x / a[i] / 解包等多重目标)."""
    names: List[str] = []
    if isinstance(node, ast.Assign):
        targets: List[ast.expr] = node.targets
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    else:
        return names
    for t in targets:
        if isinstance(t, ast.Name):
            names.append(t.id)
    return names


def _collect_params(func: "ast.FunctionDef | ast.AsyncFunctionDef", qualname: str,
                    fpath: str, syms: List[Symbol]) -> None:
    """收集函数参数(位置/仅位置/仅关键字/可变/关键字可变)."""
    args = func.args
    for a in (args.posonlyargs + args.args + args.kwonlyargs):
        syms.append(Symbol("param", qualname + "." + a.arg, a.lineno, fpath))
    if args.vararg is not None:
        syms.append(Symbol("param", qualname + ".*" + args.vararg.arg,
                           args.vararg.lineno, fpath))
    if args.kwarg is not None:
        syms.append(Symbol("param", qualname + ".**" + args.kwarg.arg,
                           args.kwarg.lineno, fpath))


def _stmt_blocks(stmt: ast.stmt) -> List[List[ast.stmt]]:
    """返回复合语句中可继续下钻的语句块列表(不进入嵌套 def/class)."""
    blocks: List[List[ast.stmt]] = []
    if isinstance(stmt, (ast.If, ast.For, ast.AsyncFor, ast.While)):
        blocks.append(stmt.body)
        blocks.append(stmt.orelse)
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        blocks.append(stmt.body)
    elif isinstance(stmt, ast.Try):
        blocks.append(stmt.body)
        blocks.append(stmt.orelse)
        blocks.append(stmt.finalbody)
        for h in stmt.handlers:
            blocks.append(h.body)
    return blocks


def _collect_local_vars(stmt_list: List[ast.stmt], qualname: str, fpath: str,
                        syms: List[Symbol]) -> None:
    """收集函数体内的局部变量赋值(不进入嵌套 def/class)."""
    for stmt in stmt_list:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            for name in _assign_names(stmt):
                syms.append(Symbol("variable", qualname + "." + name,
                                   stmt.lineno, fpath))
        for block in _stmt_blocks(stmt):
            _collect_local_vars(block, qualname, fpath, syms)


def _walk_class(cls: ast.ClassDef, qualname: str, fpath: str,
                syms: List[Symbol]) -> None:
    """遍历类体: 方法/嵌套类 -> 符号, 类属性 -> attribute."""
    for item in cls.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_name = qualname + "." + item.name
            syms.append(Symbol("method", method_name, item.lineno, fpath))
            _collect_params(item, method_name, fpath, syms)
            _collect_local_vars(item.body, method_name, fpath, syms)
        elif isinstance(item, ast.ClassDef):
            nested = qualname + "." + item.name
            syms.append(Symbol("class", nested, item.lineno, fpath))
            _walk_class(item, nested, fpath, syms)
        elif isinstance(item, (ast.Assign, ast.AnnAssign)):
            for name in _assign_names(item):
                syms.append(Symbol("attribute", qualname + "." + name,
                                   item.lineno, fpath))


def extract_python_symbols(source: str, fpath: str) -> List[Symbol]:
    """用 AST 精确提取 Python 文件中的全部符号."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        sys.stderr.write("duck-list-symbol: %s: 语法错误, 已跳过 (%s)\n" % (fpath, e))
        return []
    syms: List[Symbol] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            syms.append(Symbol("class", node.name, node.lineno, fpath))
            _walk_class(node, node.name, fpath, syms)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            syms.append(Symbol("function", node.name, node.lineno, fpath))
            _collect_params(node, node.name, fpath, syms)
            _collect_local_vars(node.body, node.name, fpath, syms)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for name in _assign_names(node):
                syms.append(Symbol("variable", name, node.lineno, fpath))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                syms.append(Symbol("import", alias.asname or alias.name,
                                   node.lineno, fpath))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                syms.append(Symbol("import", alias.asname or alias.name,
                                   node.lineno, fpath))
    return syms


# ============================== 其他语言正则提取 ==============================

# PatternSpec = (正则, 函数名捕获组序号, 额外前缀捕获组序号|None)
# 额外前缀用于 Go 的方法接收者类型(如 Server.Handle)
FuncSpec = Tuple[re.Pattern, int, Optional[int]]

# 函数定义正则(取自 duck-list-func, 覆盖 9 类语言)
FUNC_PATTERNS: Dict[str, List[FuncSpec]] = {
    "python": [
        (re.compile(r'^\s*(?:async\s+)?\bdef\b\s+(\w+)\s*\('), 1, None),
    ],
    "javascript": [
        (re.compile(r'^\s*(?:export\s+)?(?:async\s+)?\bfunction\b\s*\*?\s*(\w+)'), 1, None),
        (re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?'
                    r'(?:\([^)]*\)|[\w\s,$.]+?)\s*=>'), 1, None),
        (re.compile(r'^\s*(?:async\s+)?(?!'
                    r'if|for|while|switch|catch|function|return|typeof|new|delete|do|else|'
                    r'try|finally|with|await|yield|class|extends|default|case|break|continue|'
                    r'throw|void|in|of|this|super|import|export|debugger|enum'
                    r'\b)(\w+)\s*\([^)]*\)\s*\{'), 1, None),
    ],
    "go": [
        (re.compile(r'^\s*\bfunc\b\s*\(\s*(?:[\w\s]*\*?\s*)?([\w.]+)\s*\)\s*(\w+)\s*\('), 2, 1),
        (re.compile(r'^\s*\bfunc\b\s*(\w+)\s*\('), 1, None),
    ],
    "rust": [
        (re.compile(r'^\s*(?:pub(?:\(\w*\))?\s+)?(?:async\s+)?\bfn\b\s+(\w+)'), 1, None),
    ],
    "ruby": [
        (re.compile(r'^\s*\bdef\s+(\w+[!?]?)'), 1, None),
    ],
    "php": [
        (re.compile(r'^\s*(?:public|private|protected|static|final|abstract|readonly|\s)*'
                    r'\bfunction\b\s*\*?\s*(\w+)'), 1, None),
    ],
    "shell": [
        (re.compile(r'^\s*(\w+)\s*\(\s*\)\s*\{'), 1, None),
        (re.compile(r'^\s*\bfunction\b\s+(\w+)'), 1, None),
    ],
    "lua": [
        (re.compile(r'^\s*(?:local\s+)?\bfunction\b\s+(\w[\w.:]*)'), 1, None),
    ],
    "cfamily": [
        (re.compile(
            r'^\s*'
            r'(?:(?:public|private|protected|internal|static|final|virtual|inline|'
            r'const|constexpr|consteval|override|async|friend|unsigned|signed|'
            r'explicit|mutable|volatile|register|extern|abstract|sealed|pure)\s+)*'
            r'(?:\[\[[^\]]*\]\]\s*)*'
            r'(?:[\w:<>&*\s]+?)\s+'
            r'(?!(?:if|for|while|switch|catch|return|sizeof|typeof|alignof|await|'
            r'new|delete|throw|else|do|using|try|lock)\b)'
            r'(\w+)\s*\([^;]*$'
        ), 1, None),
    ],
}

# 类/结构体/接口正则(取自 duck-list-struct); 用于类名提取与给方法加 "ClassName." 前缀
CLASS_PATTERNS: Dict[str, Optional[re.Pattern]] = {
    "python": re.compile(r'^\s*\bclass\b\s+(\w+)'),
    "javascript": re.compile(r'^\s*(?:export\s+)?(?:default\s+)?\b(?:class|interface|enum)\b\s+(\w+)'),
    "php": re.compile(r'^\s*(?:abstract\s+|final\s+)*\bclass\b\s+(\w+)'),
    "ruby": re.compile(r'^\s*\b(?:class|module)\b\s+(\w+)'),
    "rust": re.compile(r'^\s*\bimpl\b(?:\s*<[^>]*>)?\s+(?:[\w:]+?\s+for\s+)?([\w:]+)'),
    "cfamily": re.compile(
        r'^\s*(?:(?:public|private|protected|internal|abstract|final|sealed|static|'
        r'readonly)\s+)*\b(?:class|struct|interface|enum)\b\s+(\w+)'),
    "go": None,
    "shell": None,
    "lua": None,
}

# 结构体/类型别名正则(struct/class/enum/interface/union/trait/type), 记为 class 类符号
StructSpec = Tuple[re.Pattern, int]
STRUCT_PATTERNS: Dict[str, List[StructSpec]] = {
    "python": [
        (re.compile(r'^\s*\bclass\b\s+(\w+)'), 1),
    ],
    "javascript": [
        (re.compile(r'^\s*(?:export\s+)?(?:default\s+)?\b(?:class|interface|enum)\b\s+(\w+)'), 1),
        (re.compile(r'^\s*(?:export\s+)?\btype\b\s+(\w+)\s*='), 1),
    ],
    "go": [
        (re.compile(r'^\s*\btype\b\s+(\w+)\s+\b(?:struct|interface)\b'), 1),
    ],
    "rust": [
        (re.compile(
            r'^\s*(?:pub(?:\(\w*\))?\s+|'
            r'(?:#\[[^\]]*\]\s*)*)*'
            r'\b(?:struct|enum|trait|union)\b\s+(\w+)'), 1),
        (re.compile(r'^\s*\btype\b\s+(\w+)\s*='), 1),
    ],
    "ruby": [
        (re.compile(r'^\s*\b(?:class|module)\b\s+(\w+)'), 1),
    ],
    "php": [
        (re.compile(
            r'^\s*(?:abstract\s+|final\s+)*'
            r'\b(?:class|interface|trait|enum)\b\s+(\w+)'), 1),
    ],
    "shell": [
        (re.compile(r'^\s*(?:export\s+)?\b(?:declare|typeset|local)\b\s+-[aA]\s+(\w+)'), 1),
    ],
    "lua": [
        (re.compile(r'^\s*local\s+(\w+)\s*=\s*\{'), 1),
    ],
    "cfamily": [
        (re.compile(
            r'^\s*'
            r'(?:(?:public|private|protected|internal|static|final|'
            r'abstract|sealed|readonly|partial|data|enum)\s+)*'
            r'(?:\[\[[^\]]*\]\]\s*)*'
            r'(?:#\[[^\]]*\]\]\s*)*'
            r'\b(?:class|struct|enum|interface|union|protocol|object)\b\s+'
            r'(?:<\w+>)?\s*'
            r'(\w+)'), 1),
    ],
}


def _match_func(specs: List[FuncSpec], text: str) -> Optional[Tuple[Optional[str], str]]:
    for regex, name_idx, prefix_idx in specs:
        m = regex.search(text)
        if m:
            name = m.group(name_idx)
            prefix = m.group(prefix_idx) if (prefix_idx is not None and m.group(prefix_idx)) else None
            return (prefix, name)
    return None


def _match_struct(specs: List[StructSpec], text: str) -> Optional[str]:
    for regex, name_idx in specs:
        m = regex.search(text)
        if m:
            return m.group(name_idx)
    return None


def extract_regex_symbols(lines: List[Tuple[int, str]], lang: str, fpath: str) -> List[Symbol]:
    """用正则提取非 Python 语言中的函数与类/结构体符号(精度低于 AST)."""
    func_specs = FUNC_PATTERNS.get(lang, [])
    struct_specs = STRUCT_PATTERNS.get(lang, [])
    class_pat = CLASS_PATTERNS.get(lang)
    if not func_specs and not struct_specs:
        return []

    uses_braces = lang not in INDENT_LANGS
    depth = 0
    class_stack: List[Tuple[str, Optional[int]]] = []
    indent_stack: List[Tuple[int, str]] = []
    syms: List[Symbol] = []

    for line_no, text in lines:
        # 类/结构体声明检测
        sname = _match_struct(struct_specs, text)
        if sname and not re.search(r'\{\s*\}', text):
            if uses_braces:
                class_stack.append((sname, None))
            else:
                indent = len(text) - len(text.lstrip())
                while indent_stack and indent <= indent_stack[-1][0]:
                    indent_stack.pop()
                indent_stack.append((indent, sname))

        if uses_braces:
            opens = text.count("{")
            closes = text.count("}")
            depth += opens - closes
            if class_stack and class_stack[-1][1] is None and opens > 0:
                name, _ = class_stack[-1]
                class_stack[-1] = (name, depth)
            while class_stack:
                _, body_depth = class_stack[-1]
                if body_depth is None or depth >= body_depth:
                    break
                class_stack.pop()

        # 类/结构体符号输出
        if sname is not None:
            if uses_braces:
                enclosing = class_stack[-2][0] if len(class_stack) >= 2 and class_stack[-2][1] is not None else None
            else:
                enclosing = indent_stack[-2][1] if len(indent_stack) >= 2 else None
            display = (enclosing + "." + sname) if enclosing else sname
            syms.append(Symbol("class", display, line_no, fpath))

        # 函数符号输出(方法加 "ClassName." 前缀)
        res = _match_func(func_specs, text)
        if res is not None:
            recv_prefix, fname = res
            if uses_braces:
                class_prefix = class_stack[-1][0] if class_stack and class_stack[-1][1] is not None else None
            else:
                class_prefix = indent_stack[-1][1] if indent_stack else None
            parts = [p for p in (class_prefix, recv_prefix, fname) if p]
            display = ".".join(parts)
            syms.append(Symbol("function", display, line_no, fpath))

    return syms


# ============================== 输出与 CLI ==============================

RESET = "\033[0m"
KIND_COLOR: Dict[str, str] = {
    "class": "\033[95m",      # bright magenta
    "function": "\033[92m",   # bright green
    "method": "\033[96m",     # bright cyan
    "attribute": "\033[93m",  # bright yellow
    "variable": "\033[94m",   # bright blue
    "param": "\033[91m",      # bright red
    "import": "\033[97m",     # bright white
}


def format_symbol(sym: Symbol, show_label: bool, line_number: bool, use_color: bool) -> str:
    if line_number and show_label:
        loc = "%s:%d" % (sym.file, sym.line)
    elif show_label:
        loc = sym.file
    elif line_number:
        loc = str(sym.line)
    else:
        loc = ""

    kind_field = sym.kind.ljust(9)
    if use_color:
        kind_s = KIND_COLOR.get(sym.kind, "") + kind_field + RESET
        name_s = "\033[97m" + sym.name + RESET
        loc_s = ("\033[96m" + loc + RESET) if loc else ""
    else:
        kind_s = kind_field
        name_s = sym.name
        loc_s = loc

    return "  ".join([p for p in (kind_s, name_s, loc_s) if p])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="列出代码中的符号(类/函数/方法/属性/变量/参数), Python 用 AST 精确"
                    "提取, 其他语言用正则回退(函数/类)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "符号类型(-t/--type, 逗号分隔, 缺省为全部):\n"
            "  class      类/结构体/接口\n"
            "  function   模块级函数 / 其他语言中的函数\n"
            "  method     类方法\n"
            "  attribute  类属性(类作用域内的赋值)\n"
            "  variable   模块级 / 函数内的变量赋值\n"
            "  param      函数参数\n"
            "  import     导入名(仅 Python)\n\n"
            "说明:\n"
            "  Python 文件经 AST 精确解析, 可区分上述全部类型;\n"
            "  其他语言仅用正则提取 function 与 class(变量/参数在非 Python 下不可靠, 故略去)。\n\n"
            "支持的语言(按扩展名自动识别):\n"
            "  python(.py)  javascript(.js/.ts/.jsx)  go(.go)  rust(.rs)\n"
            "  ruby(.rb)  php(.php)  shell(.sh/.bash)  lua(.lua)\n"
            "  cfamily(.c/.cpp/.cs/.java/.swift/.kt/.m 等)\n\n"
            "文件参数可混合传入文件与目录: 目录会被递归遍历(仅取已知扩展名文件,\n"
            "并跳过 node_modules/.git 等); 不传任何参数时默认遍历当前目录(.);\n"
            "管道输入需显式用 '-' 指定, 例如 'cat foo.py | duck-list-symbol -'.\n\n"
            "示例:\n"
            "  duck-list-symbol -t class,function .      # 只列出类与函数(递归当前目录)\n"
            "  duck-list-symbol --no-filename foo.py     # 单文件不显示文件名\n"
            "  duck-list-symbol -t param,attribute foo.py# 只看参数与类属性\n"
            "  cat foo.py | duck-list-symbol -          # 从管道读取(stdin)"
        ),
    )
    parser.add_argument("files", nargs="*",
                        help="要搜索的文件或目录(不传则默认遍历当前目录; '-' 表示读取 stdin)")
    parser.add_argument("-t", "--type", type=str, default=None,
                        help="按类型过滤(逗号分隔), 如 class,function,method,attribute,variable,param,import")
    parser.add_argument("--no-line-number", action="store_true", help="不显示行号")
    parser.add_argument("--lang", type=str, default=None,
                        help="强制指定语言(覆盖扩展名/Shebang 推断)")
    parser.add_argument("-H", "--with-filename", action="store_true",
                        help="总是打印文件名(类似 grep -H)")
    parser.add_argument("--no-filename", action="store_true",
                        help="不打印文件名(类似 grep -h)")
    parser.add_argument("--no-color", action="store_true", help="关闭彩色输出")
    parser.add_argument("-E", "--encoding", default="utf-8",
                        help="输入文件编码(默认 utf-8, GBK 文件可传 gbk)")
    return parser


def parse_type_filter(value: Optional[str]) -> List[str]:
    """解析 -t 类型过滤, 返回小写类型列表; 空值表示全部。"""
    if not value:
        return list(KINDS)
    selected: List[str] = []
    for part in value.split(","):
        t = part.strip().lower()
        if not t:
            continue
        if t not in KINDS:
            sys.stderr.write("duck-list-symbol: 未知类型 '%s' (支持: %s)\n"
                             % (t, ", ".join(KINDS)))
            sys.exit(2)
        selected.append(t)
    return selected


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    ensure_utf8_output()

    lang_override = args.lang
    if lang_override and lang_override not in EXT_TO_LANG.values() \
            and lang_override not in FUNC_PATTERNS:
        # 允许的语言集合 = 扩展名映射的值 + 显式支持的键
        allowed = sorted(set(list(EXT_TO_LANG.values()) + list(FUNC_PATTERNS.keys())))
        sys.stderr.write("duck-list-symbol: 未知语言 '%s' (支持: %s)\n"
                         % (lang_override, ", ".join(allowed)))
        sys.exit(2)

    selected_types = parse_type_filter(args.type)

    inputs = args.files if args.files else ["."]

    has_dir = any(inp != "-" and os.path.isdir(inp) for inp in inputs)
    show_label = (not args.no_filename) and (args.with_filename or len(inputs) > 1 or has_dir)
    line_number = not args.no_line_number
    use_color = not args.no_color

    targets: List[str] = []
    for inp in inputs:
        if inp == "-":
            targets.append("-")
        elif os.path.isdir(inp):
            targets.extend(walk_dir(inp))
        else:
            targets.append(inp)

    if not targets:
        sys.exit(0)

    for target in targets:
        if target == "-":
            if sys.stdin.isatty():
                sys.stderr.write(
                    "duck-list-symbol: 未通过管道传入数据(stdin 为终端)\n"
                    "用法: cat 文件 | duck-list-symbol -\n")
                sys.exit(2)
            lang = lang_override
            lines = list(iter_lines(sys.stdin.buffer, args.encoding))
            if lang is None and lines and lines[0][1].startswith("#!"):
                for key, value in SHEBANG_TO_LANG.items():
                    if key in lines[0][1]:
                        lang = value
                        break
            syms = _extract(lang, lines, "", args.encoding)
            _emit(syms, selected_types, False, line_number, use_color)
            continue

        fpath = target
        lang = lang_override
        if lang is None:
            lang = EXT_TO_LANG.get(os.path.splitext(fpath)[1].lower())

        if lang is None:
            try:
                with open(fpath, "rb") as fp:
                    first = fp.readline().decode("utf-8", errors="replace")
            except Exception as e:
                sys.stderr.write("duck-list-symbol: %s: %s\n" % (fpath, e))
                continue
            if first.startswith("#!"):
                for key, value in SHEBANG_TO_LANG.items():
                    if key in first:
                        lang = value
                        break

        if lang is None:
            sys.stderr.write("duck-list-symbol: %s: 无法识别语言, 用 --lang 指定\n" % fpath)
            continue

        try:
            with open(fpath, "rb") as fp:
                lines = list(iter_lines(fp, args.encoding))
        except Exception as e:
            sys.stderr.write("duck-list-symbol: %s: %s\n" % (fpath, e))
            continue

        if is_likely_minified(lines):
            sys.stderr.write("duck-list-symbol: %s: 疑似压缩代码, 已跳过\n" % fpath)
            continue

        syms = _extract(lang, lines, fpath, args.encoding)
        _emit(syms, selected_types, show_label, line_number, use_color)


def _extract(lang: Optional[str], lines: List[Tuple[int, str]], fpath: str,
            encoding: str) -> List[Symbol]:
    """根据语言选择 AST 或正则提取; Python 需要完整源码, 其余用行列表。"""
    if lang == "python":
        source = "\n".join(text for _, text in lines)
        return extract_python_symbols(source, fpath)
    return extract_regex_symbols(lines, lang, fpath) if lang else []


def _emit(syms: List[Symbol], selected_types: List[str],
          show_label: bool, line_number: bool, use_color: bool) -> None:
    for sym in syms:
        if sym.kind not in selected_types:
            continue
        print(format_symbol(sym, show_label, line_number, use_color))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(build_parser().format_help())
        sys.exit(0)
    main()
