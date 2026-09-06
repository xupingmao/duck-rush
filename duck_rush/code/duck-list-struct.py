# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/09/05
# @filename duck-list-struct.py
# @description 使用正则匹配常见编程语言中的结构体定义(struct/class/enum/
#              interface/union/trait/type 等); 嵌套定义以 "Outer.Inner" 形式输出

import sys
import io
import os
import re
import argparse
from typing import List, Optional, Dict, Tuple

# PatternSpec = (正则, 结构体名捕获组序号)
# 与 duck-list-func 不同, 此处不再需要额外前缀捕获组(接收者类型等)
PatternSpec = Tuple[re.Pattern, int]

# 所有关键字/标识符边界均使用 \b 单词边界

LANG_PATTERNS: Dict[str, List[PatternSpec]] = {
    "python": [
        # class Name(...)  /  dataclass / NamedTuple / TypedDict 本质仍是 class
        (re.compile(r'^\s*\bclass\b\s+(\w+)'), 1),
    ],
    "javascript": [
        # TS/JS: class Name  /  interface Name  /  enum Name  /  type Name =
        (re.compile(r'^\s*(?:export\s+)?(?:default\s+)?\b(?:class|interface|enum)\b\s+(\w+)'), 1),
        (re.compile(r'^\s*(?:export\s+)?\btype\b\s+(\w+)\s*='), 1),
    ],
    "go": [
        # type Name struct {...}  /  type Name interface {...}
        (re.compile(r'^\s*\btype\b\s+(\w+)\s+\b(?:struct|interface)\b'), 1),
    ],
    "rust": [
        # struct/enum/trait/union Name  /  type Name =
        (re.compile(
            r'^\s*(?:pub(?:\(\w*\))?\s+|'
            r'(?:#\[[^\]]*\]\s*)*)*'
            r'\b(?:struct|enum|trait|union)\b\s+(\w+)'), 1),
        (re.compile(r'^\s*\btype\b\s+(\w+)\s*='), 1),
    ],
    "ruby": [
        # class Name  /  module Name
        (re.compile(r'^\s*\b(?:class|module)\b\s+(\w+)'), 1),
    ],
    "php": [
        # class/interface/trait/enum Name
        (re.compile(
            r'^\s*(?:abstract\s+|final\s+)*'
            r'\b(?:class|interface|trait|enum)\b\s+(\w+)'), 1),
    ],
    "shell": [
        # shell 无原生结构体, 但支持 declare -A(关联数组)/结构体数组赋值等约定
        (re.compile(r'^\s*(?:export\s+)?\b(?:declare|typeset|local)\b\s+-[aA]\s+(\w+)'), 1),
    ],
    "lua": [
        # Lua 无 struct 关键字; 约定以 _M / metatable 形式组织, 此处匹配 module 表声明
        (re.compile(r'^\s*local\s+(\w+)\s*=\s*\{'), 1),
    ],
    # C / C++ / C# / Java / Swift / Kotlin / Objective-C 等以关键字 + 名称 形式声明
    "cfamily": [
        (re.compile(
            r'^\s*'
            r'(?:(?:public|private|protected|internal|static|final|'
            r'abstract|sealed|readonly|partial|data|enum)\s+)*'
            r'(?:\[\[[^\]]*\]\]\s*)*'      # C++ 属性说明符 [[...]]
            r'(?:#\[[^\]]*\]\]\s*)*'       # Rust 风格属性(not needed here, 防御性)
            r'\b(?:class|struct|enum|interface|union|protocol|object)\b\s+'
            r'(?:<\w+>)?\s*'               # C#/Kotlin 泛型简写 class Foo<T>
            r'(\w+)'), 1),
    ],
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
    ".ts": "javascript",   # TS 语法与 JS 基本一致
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
    """构造输出前缀, 格式为 grep 风格: '{file_path}:{line_no}: ' (可单独出现其一)."""
    if show_label and line_number:
        return f"{label}:{line_no}: "
    if show_label:
        return f"{label}: "
    if line_number:
        return f"{line_no}: "
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


def match_struct(specs: List[PatternSpec], text: str) -> Optional[str]:
    """在单行上找到第一个结构体定义匹配, 返回结构体名(否则 None)."""
    for regex, name_idx in specs:
        m = regex.search(text)
        if m:
            return m.group(name_idx)
    return None


def scan_lines(specs: List[PatternSpec], lang: str,
               lines: List[Tuple[int, str]], label: str, show_label: bool,
               line_number: bool, list_files: bool) -> bool:
    """扫描行, 命中结构体定义时输出(嵌套定义加 "Outer." 前缀); 返回是否命中."""
    uses_braces = lang not in INDENT_LANGS
    depth = 0                      # 当前花括号嵌套深度(花括号语言)
    struct_stack: List[Tuple[str, Optional[int]]] = []   # [(结构体名, body_depth|None), ...]
    indent_stack: List[Tuple[int, str]] = []             # 缩进语言: [(缩进列, 结构体名), ...]
    found = False

    for line_no, text in lines:
        opens = text.count("{")
        closes = text.count("}")
        declared: List[str] = []     # 本行新声明的结构体名(用于单行闭合后弹出)

        # --- 结构体声明检测 ---
        sname = match_struct(specs, text)
        if sname and not re.search(r'\{\s*\}', text):   # 跳过空声明 class A {}
            if uses_braces:
                struct_stack.append((sname, None))
                declared.append(sname)
            else:
                indent = len(text) - len(text.lstrip())
                while indent_stack and indent <= indent_stack[-1][0]:
                    indent_stack.pop()
                indent_stack.append((indent, sname))

        # --- 花括号深度更新 ---
        if uses_braces:
            depth += opens - closes
            # 刚声明且遇到首个 '{' 时, 记录结构体体所在深度
            if struct_stack and struct_stack[-1][1] is None and opens > 0:
                name, _ = struct_stack[-1]
                struct_stack[-1] = (name, depth)
            # 结构体体结束(右花括号匹配)时弹出
            while struct_stack:
                _, body_depth = struct_stack[-1]
                if body_depth is None or depth >= body_depth:
                    break
                struct_stack.pop()
            # 本行内花括号即开即合(如 enum Color { Red, Green }): 它无法包裹后续行,
            # 故将其从包含栈弹出, 避免误作为后续顶层结构体的前缀
            if opens > 0 and opens == closes:
                for _ in declared:
                    if struct_stack:
                        struct_stack.pop()

        if sname is None:
            continue

        if uses_braces:
            enclosing = struct_stack[-2][0] if len(struct_stack) >= 2 and struct_stack[-2][1] is not None else None
        else:
            enclosing = indent_stack[-2][1] if len(indent_stack) >= 2 else None

        display = (enclosing + "." + sname) if enclosing else sname

        found = True
        if list_files:
            continue
        print(format_prefix(label, line_no, show_label, line_number) + display)

    return found


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="使用正则匹配常见编程语言中的结构体定义(struct/class/enum/"
                    "interface/union/trait/type 等); 嵌套定义以 Outer.Inner 形式输出",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "支持的语言(按文件扩展名自动识别):\n"
            "  python(.py)  javascript(.js/.ts/.jsx)  go(.go)  rust(.rs)\n"
            "  ruby(.rb)  php(.php)  shell(.sh/.bash)  lua(.lua)\n"
            "  cfamily(.c/.cpp/.cs/.java/.swift/.kt/.m 等)\n\n"
            "可用 --lang 强制指定语言, 支持: " + ", ".join(sorted(LANG_PATTERNS.keys())) + "\n\n"
            "文件参数(file)可混合传入文件与目录: 目录会被递归遍历(仅取已知扩展名文件,\n"
            "并跳过 node_modules/.git 等); 不传任何参数时默认遍历当前目录(.);\n"
            "管道输入需显式用 '-' 指定, 例如 'cat foo.go | duck-list-struct -'.\n\n"
            "示例:\n"
            "  duck-list-struct -n src/foo.go       # 列出结构体及行号\n"
            "  duck-list-struct -l .               # 仅列出含结构体定义的文件(递归当前目录)\n"
            "  cat src/foo.rs | duck-list-struct - # 从管道读取(stdin)\n"
            "  duck-list-struct -o src/            # 递归目录, 只打印结构体名"
        ),
    )
    parser.add_argument("files", nargs="*",
                        help="要搜索的文件或目录(不传则默认遍历当前目录; '-' 表示读取 stdin)")
    parser.add_argument("-n", "--line-number", action="store_true",
                        help="显示行号(默认即显示, 此参数仅为兼容保留)")
    parser.add_argument("--no-line-number", action="store_true", help="不显示行号")
    parser.add_argument("-l", "--files-with-matches", action="store_true",
                        help="只打印含结构体定义的文件名(类似 grep -l)")
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
        sys.stderr.write("duck-list-struct: 未知语言 '%s' (支持: %s)\n"
                         % (lang_override, ", ".join(sorted(LANG_PATTERNS.keys()))))
        sys.exit(2)

    inputs = args.files if args.files else ["."]

    # 是否显示文件名标签: 多个输入 / 含目录 / 显式 -H 时显示(除非 --no-filename)
    has_dir = any(inp != "-" and os.path.isdir(inp) for inp in inputs)
    show_label = (not args.no_filename) and (args.with_filename or len(inputs) > 1 or has_dir)

    # 行号默认显示(文件名后即可见); --no-line-number 可关闭, -n 仅为兼容保留
    line_number = args.line_number or (not args.no_line_number)

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
                    "duck-list-struct: 未通过管道传入数据(stdin 为终端)\n"
                    "用法: cat 文件 | duck-list-struct -\n")
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
            if not specs:
                if lang is None:
                    sys.stderr.write("duck-list-struct: 无法识别语言, 用 --lang 指定\n")
                else:
                    sys.stderr.write("duck-list-struct: 未知语言 '%s'\n" % lang)
                sys.exit(2)
            if is_likely_minified(lines):
                sys.stderr.write("duck-list-struct: 疑似压缩代码, 已跳过\n")
                sys.exit(2)
            scan_lines(specs, lang, lines, "", False,
                       line_number, args.files_with_matches)
            continue

        fpath = target
        lang = lang_override
        if lang is None:
            ext = os.path.splitext(fpath)[1].lower()
            lang = EXT_TO_LANG.get(ext)
        specs = LANG_PATTERNS.get(lang) if lang else None

        if not specs:
            # 未知扩展名: 用 shebang 推断
            try:
                with open(fpath, "rb") as fp:
                    first = fp.readline().decode("utf-8", errors="replace")
            except Exception as e:
                sys.stderr.write("duck-list-struct: %s: %s\n" % (fpath, e))
                continue
            if first.startswith("#!"):
                for key, value in SHEBANG_TO_LANG.items():
                    if key in first:
                        lang = value
                        break
            specs = LANG_PATTERNS.get(lang) if lang else None

        if not specs:
            sys.stderr.write("duck-list-struct: %s: 无法识别语言, 用 --lang 指定\n" % fpath)
            continue

        try:
            with open(fpath, "rb") as fp:
                lines = list(iter_lines(fp, args.encoding))
        except Exception as e:
            sys.stderr.write("duck-list-struct: %s: %s\n" % (fpath, e))
            continue

        if is_likely_minified(lines):
            sys.stderr.write("duck-list-struct: %s: 疑似压缩代码, 已跳过\n" % fpath)
            continue

        hit = scan_lines(specs, lang, lines, fpath, show_label,
                         line_number, args.files_with_matches)
        if args.files_with_matches and hit:
            print(fpath)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(build_parser().format_help())
        sys.exit(0)
    main()
