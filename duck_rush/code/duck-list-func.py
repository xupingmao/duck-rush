# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/09/05
# @filename duck-list-func.py
# @description 使用正则匹配常见编程语言中的函数定义, 单词边界统一使用 \b;
#              类/结构体/impl 中的方法会以 "ClassName.funcName" 形式输出

import sys
import io
import os
import re
import argparse
from typing import List, Optional, Dict, Tuple

# PatternSpec = (正则, 函数名捕获组序号, 额外前缀捕获组序号|None)
# 额外前缀用于 Go 的方法接收者类型(如 Server.Handle)
PatternSpec = Tuple[re.Pattern, int, Optional[int]]

# 所有关键字/标识符边界均使用 \b 单词边界

# JavaScript 关键字(对象/类方法简写匹配时需排除, 否则 if/for/while/catch 等会被误判为函数)
_JS_KEYWORDS = (
    "if", "for", "while", "switch", "catch", "function", "return", "typeof",
    "new", "delete", "do", "else", "try", "finally", "with", "await", "yield",
    "class", "extends", "default", "case", "break", "continue", "throw", "void",
    "in", "of", "this", "super", "import", "export", "debugger", "enum",
)
JS_KEYWORD_RE = "(?:" + "|".join(_JS_KEYWORDS) + ")"

LANG_PATTERNS: Dict[str, List[PatternSpec]] = {
    "python": [
        # def name(...)  /  async def name(...)
        (re.compile(r'^\s*(?:async\s+)?\bdef\b\s+(\w+)\s*\('), 1, None),
    ],
    "javascript": [
        # function 声明/表达式, 含 generator(function*) 与 async
        (re.compile(r'^\s*(?:export\s+)?(?:async\s+)?\bfunction\b\s*\*?\s*(\w+)'), 1, None),
        # 箭头函数赋值: const/let/var name = (...) => 或 name = arg =>
        (re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?'
                    r'(?:\([^)]*\)|[\w\s,$.]+?)\s*=>'), 1, None),
        # 对象/类方法简写: name(...) {  (排除控制流/关键字, 否则 if/for/while 等会被误判)
        (re.compile(r'^\s*(?:async\s+)?(?!'
                    + JS_KEYWORD_RE + r'\b)(\w+)\s*\([^)]*\)\s*\{'), 1, None),
    ],
    "go": [
        # func (receiver) name(...)  -> 组1=接收者类型, 组2=函数名
        (re.compile(r'^\s*\bfunc\b\s*\(\s*(?:[\w\s]*\*?\s*)?([\w.]+)\s*\)\s*(\w+)\s*\('), 2, 1),
        # func name(...)
        (re.compile(r'^\s*\bfunc\b\s*(\w+)\s*\('), 1, None),
    ],
    "rust": [
        (re.compile(r'^\s*(?:pub(?:\(\w*\))?\s+)?(?:async\s+)?\bfn\b\s+(\w+)'), 1, None),
    ],
    "ruby": [
        # def method_name   (Ruby 方法名可含 ! ?)
        (re.compile(r'^\s*\bdef\s+(\w+[!?]?)'), 1, None),
    ],
    "php": [
        (re.compile(r'^\s*(?:public|private|protected|static|final|abstract|readonly|\s)*'
                    r'\bfunction\b\s*\*?\s*(\w+)'), 1, None),
    ],
    "shell": [
        # name() {  或 function name {
        (re.compile(r'^\s*(\w+)\s*\(\s*\)\s*\{'), 1, None),
        (re.compile(r'^\s*\bfunction\b\s+(\w+)'), 1, None),
    ],
    "lua": [
        (re.compile(r'^\s*(?:local\s+)?\bfunction\b\s+(\w[\w.:]*)'), 1, None),
    ],
    # C / C++ / C# / Java / Swift / Kotlin / Objective-C 等以 "返回类型 函数名(" 形式定义
    "cfamily": [
        (re.compile(
            r'^\s*'
            r'(?:(?:public|private|protected|internal|static|final|virtual|inline|'
            r'const|constexpr|consteval|override|async|friend|unsigned|signed|'
            r'explicit|mutable|volatile|register|extern|abstract|sealed|pure)\s+)*'
            r'(?:\[\[[^\]]*\]\]\s*)*'   # C++ 属性说明符 [[...]]
            r'(?:[\w:<>&*\s]+?)\s+'
            r'(?!(?:if|for|while|switch|catch|return|sizeof|typeof|alignof|await|'
            r'new|delete|throw|else|do|using|try|lock)\b)'
            r'(\w+)\s*\([^;]*$'
        ), 1, None),
    ],
}

# 类/结构体/接口声明, 捕获组 1 为名称; 用于给方法名加 "ClassName." 前缀
# None 表示该语言无类(如 go 用接收者, lua 用 module. 已含在名字里)
CLASS_PATTERNS: Dict[str, Optional[re.Pattern]] = {
    "python": re.compile(r'^\s*\bclass\b\s+(\w+)'),
    "javascript": re.compile(r'^\s*(?:export\s+)?(?:default\s+)?\bclass\b\s+(\w+)'),
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

# 使用缩进而非花括号界定作用域的语言
INDENT_LANGS = ("python", "ruby")

# 文件扩展名 -> 语言
EXT_TO_LANG: Dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "javascript",   # TS 函数语法与 JS 基本一致
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
    ".m": "cfamily",       # Objective-C
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

# 目录递归时跳过的目录名(避免扫描依赖/构建产物等造成卡顿)
IGNORE_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".tox",
    "dist", "build", ".idea", ".vscode", "site-packages", ".mypy_cache",
})


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


def iter_lines(stream, encoding: str):
    """从二进制流逐行解码, 返回 (行号, 去尾部换行的内容)"""
    for line_no, raw in enumerate(stream, 1):
        yield line_no, raw.decode(encoding, errors="replace").rstrip("\n")


def walk_dir(root: str) -> List[str]:
    """递归遍历目录, 仅返回扩展名可识别语言(EXT_TO_LANG)的文件, 跳过 IGNORE_DIRS."""
    result: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # 原地过滤, 避免继续深入无关目录
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in EXT_TO_LANG:
                result.append(os.path.join(dirpath, fn))
    return result


def format_prefix(label: str, line_no: int, show_label: bool, line_number: bool) -> str:
    parts = []
    if show_label:
        parts.append(label)
    if line_number:
        parts.append(f"{line_no:4d}")
    if parts:
        return " │ ".join(parts) + " │ "
    return ""


# 单行字符数超过该阈值即视为疑似压缩/打包代码(如压缩后的 js 单行可达数万字符)
MINIFIED_LINE_LEN = 10000


def is_likely_minified(lines: List[Tuple[int, str]]) -> bool:
    """判断是否为压缩过的代码: 存在超长单行, 或行数极少却整体极密."""
    if not lines:
        return False
    max_len = max(len(text) for _, text in lines)
    if max_len > MINIFIED_LINE_LEN:
        return True
    # 行数很少(<=3)且存在较长单行(>2000), 多为打包后的少量长行
    if len(lines) <= 3 and max_len > 2000:
        return True
    return False


def match_line(specs: List[PatternSpec], text: str) -> Optional[Tuple[Optional[str], str]]:
    """在单行上找到第一个函数定义匹配, 返回 (额外前缀|None, 函数名)."""
    for regex, name_idx, prefix_idx in specs:
        m = regex.search(text)
        if m:
            name = m.group(name_idx)
            prefix = m.group(prefix_idx) if prefix_idx is not None and m.group(prefix_idx) else None
            return (prefix, name)
    return None


def scan_lines(specs: List[PatternSpec], class_pat: Optional[re.Pattern], lang: str,
               lines: List[Tuple[int, str]], label: str, show_label: bool,
               line_number: bool, list_files: bool) -> bool:
    """扫描行, 命中函数定义时输出(类方法加 "ClassName." 前缀); 返回是否命中. """
    uses_braces = lang not in INDENT_LANGS
    depth = 0                      # 当前花括号嵌套深度(花括号语言)
    class_stack: List[Tuple[str, Optional[int]]] = []   # 花括号语言: [(类名, body_depth|None), ...]
    indent_stack: List[Tuple[int, str]] = []            # 缩进语言: [(缩进列, 类名), ...]
    found = False

    for line_no, text in lines:
        # --- 类/结构体/接口声明检测 ---
        if class_pat:
            cm = class_pat.search(text)
            if cm and not re.search(r'\{\s*\}', text):   # 跳过 class A {} 这种空声明
                cname = cm.group(1)
                if uses_braces:
                    class_stack.append((cname, None))
                else:
                    indent = len(text) - len(text.lstrip())
                    while indent_stack and indent <= indent_stack[-1][0]:
                        indent_stack.pop()
                    indent_stack.append((indent, cname))

        # --- 花括号深度更新 ---
        if uses_braces:
            opens = text.count("{")
            closes = text.count("}")
            depth += opens - closes
            # 刚声明且遇到首个 '{' 时, 记录方法体所在深度
            if class_stack and class_stack[-1][1] is None and opens > 0:
                name, _ = class_stack[-1]
                class_stack[-1] = (name, depth)
            # 类体结束(右花括号匹配)时弹出
            while class_stack:
                _, body_depth = class_stack[-1]
                if body_depth is None or depth >= body_depth:
                    break
                class_stack.pop()

        # --- 函数定义匹配 ---
        res = match_line(specs, text)
        if res is None:
            continue
        recv_prefix, fname = res

        if uses_braces:
            class_prefix = class_stack[-1][0] if class_stack and class_stack[-1][1] is not None else None
        else:
            class_prefix = indent_stack[-1][1] if indent_stack else None

        parts = [p for p in (class_prefix, recv_prefix, fname) if p]
        display = ".".join(parts)

        found = True
        if list_files:
            continue
        # 默认输出 "ClassName.funcName" 形式的限定名; -o 同样输出限定名
        print(format_prefix(label, line_no, show_label, line_number) + display)

    return found


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="使用正则匹配常见编程语言中的函数定义(单词边界使用 \\b); "
                    "类的方法以 ClassName.funcName 形式输出",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "支持的语言(按文件扩展名自动识别):\n"
            "  python(.py)  javascript(.js/.ts/.jsx)  go(.go)  rust(.rs)\n"
            "  ruby(.rb)  php(.php)  shell(.sh/.bash)  lua(.lua)\n"
            "  cfamily(.c/.cpp/.cs/.java/.swift/.kt/.m 等)\n\n"
            "可用 --lang 强制指定语言, 支持: " + ", ".join(sorted(LANG_PATTERNS.keys())) + "\n\n"
            "文件参数(file)可混合传入文件与目录: 目录会被递归遍历(仅取已知扩展名文件,\n"
            "并跳过 node_modules/.git 等); 不传任何参数时默认遍历当前目录(.);\n"
            "管道输入需显式用 '-' 指定, 例如 'cat foo.py | duck-list-func -'.\n\n"
            "示例:\n"
            "  duck-list-func -n src/foo.py        # 列出函数及行号\n"
            "  duck-list-func -l .                 # 仅列出含函数定义的文件(递归当前目录)\n"
            "  cat src/foo.py | duck-list-func -   # 从管道读取(stdin)\n"
            "  duck-list-func -o src/              # 递归目录, 只打印函数名(含 ClassName.)"
        ),
    )
    parser.add_argument("files", nargs="*",
                        help="要搜索的文件或目录(不传则默认遍历当前目录; '-' 表示读取 stdin)")
    parser.add_argument("-n", "--line-number", action="store_true", help="显示行号")
    parser.add_argument("-l", "--files-with-matches", action="store_true",
                        help="只打印含函数定义的文件名(类似 grep -l)")
    parser.add_argument("--lang", type=str, default=None,
                        help="强制指定语言(覆盖扩展名/Shebang 推断)")
    parser.add_argument("-H", "--with-filename", action="store_true",
                        help="总是打印文件名(类似 grep -H)")
    parser.add_argument("--no-filename", action="store_true",
                        help="不打印文件名(类似 grep -h)")
    parser.add_argument("-E", "--encoding", default="utf-8",
                        help="输入文件编码(默认 utf-8, GBK 文件可传 gbk)")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    ensure_utf8_output()

    lang_override = args.lang
    if lang_override and lang_override not in LANG_PATTERNS:
        sys.stderr.write("duck-list-func: 未知语言 '%s' (支持: %s)\n"
                         % (lang_override, ", ".join(sorted(LANG_PATTERNS.keys()))))
        sys.exit(2)

    inputs = args.files if args.files else ["."]

    # 是否显示文件名标签: 多个输入 / 含目录 / 显式 -H 时显示(除非 --no-filename)
    has_dir = any(inp != "-" and os.path.isdir(inp) for inp in inputs)
    show_label = (not args.no_filename) and (args.with_filename or len(inputs) > 1 or has_dir)

    # 展开输入: 目录递归遍历; "-" 表示读取管道(stdin), 需显式指定
    targets: List[str] = []
    for inp in inputs:
        if inp == "-":
            targets.append("-")
        elif os.path.isdir(inp):
            targets.extend(walk_dir(inp))
        else:
            targets.append(inp)

    if not targets:
        # 目录遍历未匹配到任何已知扩展名的文件
        sys.exit(0)

    for target in targets:
        if target == "-":
            # 管道输入通过 "-" 参数显式指定, 避免交互终端下误阻塞
            if sys.stdin.isatty():
                sys.stderr.write(
                    "duck-list-func: 未通过管道传入数据(stdin 为终端)\n"
                    "用法: cat 文件 | duck-list-func -\n")
                sys.exit(2)
            lang = lang_override
            lines = list(iter_lines(sys.stdin.buffer, args.encoding))
            if lang is None and lines:
                first = lines[0][1]
                if first.startswith("#!"):
                    for key, value in SHEBANG_TO_LANG.items():
                        if key in first:
                            lang = value
                            break
            specs = LANG_PATTERNS.get(lang) if lang else None
            class_pat = CLASS_PATTERNS.get(lang) if lang else None
            if not specs:
                if lang is None:
                    sys.stderr.write("duck-list-func: 无法识别语言, 用 --lang 指定\n")
                else:
                    sys.stderr.write("duck-list-func: 未知语言 '%s'\n" % lang)
                sys.exit(2)
            if is_likely_minified(lines):
                sys.stderr.write("duck-list-func: 疑似压缩代码, 已跳过\n")
                sys.exit(2)
            scan_lines(specs, class_pat, lang, lines, "", False,
                       args.line_number, args.files_with_matches)
            continue

        fpath = target
        lang = lang_override
        if lang is None:
            ext = os.path.splitext(fpath)[1].lower()
            lang = EXT_TO_LANG.get(ext)
        specs = LANG_PATTERNS.get(lang) if lang else None
        class_pat = CLASS_PATTERNS.get(lang) if lang else None

        if not specs:
            # 未知扩展名: 用 shebang 推断
            try:
                with open(fpath, "rb") as fp:
                    first = fp.readline().decode("utf-8", errors="replace")
            except Exception as e:
                sys.stderr.write("duck-list-func: %s: %s\n" % (fpath, e))
                continue
            if first.startswith("#!"):
                for key, value in SHEBANG_TO_LANG.items():
                    if key in first:
                        lang = value
                        break
            specs = LANG_PATTERNS.get(lang) if lang else None
            class_pat = CLASS_PATTERNS.get(lang) if lang else None

        if not specs:
            sys.stderr.write("duck-list-func: %s: 无法识别语言, 用 --lang 指定\n" % fpath)
            continue

        try:
            with open(fpath, "rb") as fp:
                lines = list(iter_lines(fp, args.encoding))
        except Exception as e:
            sys.stderr.write("duck-list-func: %s: %s\n" % (fpath, e))
            continue

        if is_likely_minified(lines):
            sys.stderr.write("duck-list-func: %s: 疑似压缩代码, 已跳过\n" % fpath)
            continue

        hit = scan_lines(specs, class_pat, lang, lines, fpath, show_label,
                         args.line_number, args.files_with_matches)
        if args.files_with_matches and hit:
            print(fpath)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(build_parser().format_help())
        sys.exit(0)
    main()
