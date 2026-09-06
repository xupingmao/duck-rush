# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/09/06
# @filename duck-find-symbol.py
# @description 搜索某个符号(名字)在代码中出现的全部代码行。自动把名字转为
#              camelCase / snake_case / PascalCase / SCREAMING_SNAKE 等多种形式并大小写
#              不敏感匹配(与 duck-find-assign 同款命名变体); 默认剥离注释以减少噪音。
#
# 与 duck-find-assign 的差异: 此处匹配"符号出现的任意代码行"(而非仅赋值),
# 因此不引入 setXxx setter 形式, 其余 CLI / 输出 / 语言识别特性保持一致。
# 命名变体逻辑复用 duck_utils.find_assign.name, 注释剥离复用其 language plugin。

import sys
import io
import os
import re
import argparse
from typing import Any, List, Optional, Tuple

from duck_utils.find_assign.name import NameVariants
from duck_utils.find_assign.engine import strip_comments
from duck_utils.find_assign.lang import (
    GENERIC_PLUGIN,
    KNOWN_EXTENSIONS,
    LanguagePlugin,
    get_plugin_by_ext,
    get_plugin_by_name,
    list_lang_names,
)

# 浅色(明亮)配色, 满足 AGENTS 规范(深色背景下清晰可读)
C_FILE = "\033[94m"    # bright blue
C_LINE = "\033[96m"    # bright cyan
C_MATCH = "\033[93m"   # bright yellow
C_RESET = "\033[0m"

# 单文件大小上限(字节), 超过则跳过, 避免大文件/二进制卡顿
DEFAULT_MAX_SIZE = 5 * 1024 * 1024

# 目录递归时跳过的目录名(依赖/构建产物等)
IGNORE_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".tox",
    "dist", "build", ".idea", ".vscode", "site-packages", ".mypy_cache",
    ".svn",
})


def ensure_utf8_output() -> None:
    """强制以 UTF-8 输出, 避免 Windows 控制台代码页导致的中文乱码。"""
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


def build_pattern(name: str) -> Any:
    """根据名字生成命名变体, 构造大小写不敏感的整词匹配正则。"""
    variants = NameVariants(name).identifiers
    if not variants:
        sys.stderr.write("duck-find-symbol: 名字 '%s' 无法解析为标识符\n" % name)
        sys.exit(2)
    escaped = [re.escape(v) for v in variants if v]
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)


def highlight(line: str, pattern: Any) -> str:
    """高亮行内第一个命中区间。"""
    m = pattern.search(line)
    if not m:
        return line
    s, e = m.span()
    return line[:s] + C_MATCH + line[s:e] + C_RESET + line[e:]


def _read_text(fpath: str, encoding: str) -> Optional[str]:
    """按编码尝试读取文本, 失败返回 None。"""
    for enc in (encoding, "utf-8", "gbk", "latin-1"):
        if enc is None:
            continue
        try:
            with open(fpath, encoding=enc, errors="strict") as fp:
                return fp.read()
        except (UnicodeDecodeError, LookupError):
            continue
        except OSError:
            return None
    return None


def search_text(text: str, plugin: LanguagePlugin, pattern: Any,
                strip_comments_flag: bool) -> List[Tuple[int, str, Any]]:
    """在文本中按 pattern 搜索, 返回 [(行号, 行文本, pattern)]。"""
    if strip_comments_flag and (plugin.block_comments or plugin.line_comments):
        text = strip_comments(text, plugin)
    matches: List[Tuple[int, str, Any]] = []
    for line_no, line in enumerate(text.split("\n"), 1):
        if pattern.search(line):
            matches.append((line_no, line, pattern))
    return matches


def plugin_for(fpath: str, lang_plugin: Optional[LanguagePlugin]) -> LanguagePlugin:
    ext = os.path.splitext(fpath)[1].lower()
    plugin = get_plugin_by_ext(ext)
    if plugin is None:
        plugin = lang_plugin or GENERIC_PLUGIN
    return plugin


def search_file(fpath: str, pattern: Any, encoding: str, max_size: int,
               lang_plugin: Optional[LanguagePlugin],
               strip_comments_flag: bool) -> Optional[Tuple[str, List[Tuple[int, str, Any]]]]:
    try:
        size = os.path.getsize(fpath)
    except OSError:
        return None
    if size > max_size:
        return None
    text = _read_text(fpath, encoding)
    if text is None:
        return None
    plugin = plugin_for(fpath, lang_plugin)
    matches = search_text(text, plugin, pattern, strip_comments_flag)
    return (fpath, matches) if matches else None


def search_dir(root: str, pattern: Any, encoding: str, max_size: int,
              lang_plugin: Optional[LanguagePlugin],
              strip_comments_flag: bool) -> List[Tuple[str, List[Tuple[int, str, Any]]]]:
    results: List[Tuple[str, List[Tuple[int, str, Any]]]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in KNOWN_EXTENSIONS:
                continue
            res = search_file(os.path.join(dirpath, fn), pattern, encoding,
                              max_size, lang_plugin, strip_comments_flag)
            if res is not None:
                results.append(res)
    return results


def search_stdin(pattern: Any, lang_plugin: Optional[LanguagePlugin],
                strip_comments_flag: bool, label: str = "-") \
        -> Optional[Tuple[str, List[Tuple[int, str, Any]]]]:
    plugin = lang_plugin or GENERIC_PLUGIN
    data = sys.stdin.read()
    matches = search_text(data, plugin, pattern, strip_comments_flag)
    return (label, matches) if matches else None


def search_targets(targets: List[str], pattern: Any, encoding: str, max_size: int,
                  lang: Optional[str],
                  strip_comments_flag: bool) -> List[Tuple[str, List[Tuple[int, str, Any]]]]:
    lang_plugin = get_plugin_by_name(lang) if lang else None
    results: List[Tuple[str, List[Tuple[int, str, Any]]]] = []
    for target in targets:
        if target == "-":
            res = search_stdin(pattern, lang_plugin, strip_comments_flag)
            if res is not None:
                results.append(res)
        elif os.path.isdir(target):
            results.extend(search_dir(target, pattern, encoding, max_size,
                                     lang_plugin, strip_comments_flag))
        else:
            res = search_file(target, pattern, encoding, max_size,
                              lang_plugin, strip_comments_flag)
            if res is not None:
                results.append(res)
    return results


def print_results(results: List[Tuple[str, List[Tuple[int, str, Any]]]],
                  show_label: bool, line_number: bool,
                  files_with_matches: bool) -> int:
    total = 0
    for fpath, matches in results:
        total += len(matches)
        if files_with_matches:
            print(fpath)
            continue
        print("")
        print(C_FILE + fpath + C_RESET + "  (%d matches)" % len(matches))
        for line_no, line, pattern in matches:
            prefix = ""
            if show_label:
                # file:line 形式, 中间不留空格、行号后不加冒号, 方便 IDE 终端点击跳转
                prefix += C_FILE + fpath + C_RESET + ":"
            if line_number:
                prefix += C_LINE + "%d" % line_no + C_RESET
            print(prefix + " " + highlight(line, pattern))
    return total


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="搜索某个符号在代码中出现的全部代码行(自动驼峰/下划线互转, "
                    "大小写不敏感, 默认剥离注释)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "命名变体: 输入 userName / user_name 都会同时匹配 userName、UserName、\n"
            "user_name、USER_NAME, 且大小写不敏感; 仅做整词匹配(如 count 不会误中 counter\n"
            "或 totalCount)。\n\n"
            "支持语言(按扩展名自动识别, 用于注释剥离):\n"
            "  python(.py)  go(.go)  javascript(.js/.ts/.jsx)  java(.java)\n"
            "  c(.c/.h)  cpp(.cpp/.cc/.hpp 等)\n"
            "可用 --lang 强制指定语言(覆盖扩展名推断, 支持: "
            + ", ".join(list_lang_names()) + ")。\n\n"
            "目标参数可混合文件与目录: 目录递归遍历(仅取已知扩展名, 跳过 node_modules/.git 等);\n"
            "不传目标时默认搜索当前目录(.); 管道输入用 '-' 显式指定, 例如:\n"
            "  cat foo.py | duck-find-symbol userName -\n\n"
            "示例:\n"
            "  duck-find-symbol userName .             # 递归当前目录搜出现位置\n"
            "  duck-find-symbol user_name src/a.py      # 指定文件\n"
            "  duck-find-symbol count -l src/           # 仅列文件名\n"
            "  duck-find-symbol total --include-comments  # 连注释也搜\n"
            "  cat a.go | duck-find-symbol name - --lang go"
        ),
    )
    parser.add_argument("name", help="要搜索的符号名字(任意命名风格)")
    parser.add_argument("targets", nargs="*",
                        help="文件或目录(不传则默认当前目录; '-' 表示读 stdin)")
    parser.add_argument("--lang", type=str, default=None,
                        help="强制指定语言(覆盖扩展名推断, 对 stdin 必需)")
    parser.add_argument("-E", "--encoding", default="utf-8",
                        help="文件编码(默认 utf-8, GBK 文件可传 gbk)")
    parser.add_argument("--max-size", type=int, default=DEFAULT_MAX_SIZE // (1024 * 1024),
                        metavar="MB", help="跳过超过该大小(MB)的文件(默认 5)")
    parser.add_argument("-C", "--include-comments", action="store_true",
                        help="连注释行也一并搜索(默认会剥离注释以减少噪音)")
    parser.add_argument("-l", "--files-with-matches", action="store_true",
                        help="只打印含匹配的文件名(类似 grep -l)")
    parser.add_argument("-H", "--with-filename", action="store_true",
                        help="总是打印文件名(类似 grep -H)")
    parser.add_argument("--no-filename", action="store_true",
                        help="不打印文件名(类似 grep -h)")
    parser.add_argument("-n", "--line-number", action="store_true",
                        help="显示行号(默认即显示, 仅为兼容保留)")
    parser.add_argument("--no-line-number", action="store_true",
                        help="不显示行号")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    ensure_utf8_output()

    if args.lang is not None and args.lang not in list_lang_names():
        sys.stderr.write("duck-find-symbol: 未知语言 '%s' (支持: %s)\n"
                         % (args.lang, ", ".join(list_lang_names())))
        sys.exit(2)

    targets = args.targets if args.targets else ["."]
    has_dir = any(t != "-" and os.path.isdir(t) for t in targets)
    show_label = (not args.no_filename) and (args.with_filename or len(targets) > 1 or has_dir)
    line_number = args.line_number or (not args.no_line_number)

    # 管道输入需显式 '-' 指定; 终端下直接 '-' 视为误用
    if "-" in targets and sys.stdin.isatty():
        sys.stderr.write(
            "duck-find-symbol: 未通过管道传入数据(stdin 为终端)\n"
            "用法: cat 文件 | duck-find-symbol NAME -\n")
        sys.exit(2)

    pattern = build_pattern(args.name)

    results = search_targets(
        targets, pattern, args.encoding,
        args.max_size * 1024 * 1024, args.lang,
        not args.include_comments,
    )
    total = print_results(results, show_label, line_number, args.files_with_matches)

    if not results:
        sys.stderr.write("duck-find-symbol: 未找到符号 '%s' 的出现\n" % args.name)
    else:
        sys.stderr.write("duck-find-symbol: 在 %d 个文件中共 %d 处命中\n"
                         % (len(results), total))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(build_parser().format_help())
        sys.exit(0)
    main()
