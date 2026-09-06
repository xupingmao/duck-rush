# -*- coding:utf-8 -*-
# @filename find_assign_engine.py
# @description 赋值搜索核心引擎(高内聚): 负责文件读取、注释剥离、逐行匹配与结果收集。
#
# 引擎只依赖 LanguagePlugin 接口(见 find_assign_lang)与 NameVariants(见
# find_assign_name), 不内含任何具体语言规则 —— 语言差异全部通过 plugin 注入,
# 从而实现"搜索逻辑高内聚、语言匹配逻辑低耦合"。

import os
import re
from typing import Any, List, Optional, Tuple

from find_assign_name import NameVariants
from find_assign_lang import (GENERIC_PLUGIN, KNOWN_EXTENSIONS, LanguagePlugin,
                              get_plugin_by_ext, get_plugin_by_name)

# re.compile 返回值在 3.6 运行期没有 re.Pattern 这个名字
Pattern = Any

# 单文件大小上限(字节), 超过则跳过, 避免大文件/二进制卡顿
DEFAULT_MAX_SIZE = 5 * 1024 * 1024

# 目录递归时跳过的目录名(依赖/构建产物等)
IGNORE_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".tox",
    "dist", "build", ".idea", ".vscode", "site-packages", ".mypy_cache",
    ".svn",
})

# 单/双/反引号字符串定界符
_STRING_CHARS = {'"', "'", "`"}

# 一个文件的命中结果: (路径, [(行号, 行文本, 命中正则)])
FileResult = Tuple[str, List[Tuple[int, str, Pattern]]]


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


def _strip_block_comments(content: str, blocks: Tuple[Tuple[str, str], ...]) -> str:
    """字符串感知地删除块注释; 用空格替换(保留换行以维持行号)。"""
    if not blocks:
        return content
    out: List[str] = []
    i = 0
    n = len(content)
    quote: Optional[str] = None
    while i < n:
        c = content[i]
        if quote is not None:
            if c == "\\":
                out.append(c)
                i += 1
                if i < n:
                    out.append(content[i])
                    i += 1
                continue
            if c == quote:
                quote = None
            out.append(c)
            i += 1
            continue
        # Python 三引号字符串(视为字符串, 不被块注释规则影响)
        if content.startswith('"""', i) or content.startswith("'''", i):
            q = content[i:i + 3]
            j = content.find(q, i + 3)
            j = n if j == -1 else j + 3
            out.append(re.sub(r"[^\n]", " ", content[i:j]))
            i = j
            continue
        if c in _STRING_CHARS:
            quote = c
            out.append(c)
            i += 1
            continue
        matched = False
        for start, end in blocks:
            if content.startswith(start, i):
                j = content.find(end, i + len(start))
                j = n if j == -1 else j + len(end)
                out.append(re.sub(r"[^\n]", " ", content[i:j]))
                i = j
                matched = True
                break
        if matched:
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _strip_line_comment(line: str, markers: Tuple[str, ...]) -> str:
    """字符串感知地删除行注释; 用空格替换注释部分(保留换行)。"""
    if not markers:
        return line
        # 长标记优先(// 在 # 之前)
    ordered = sorted(set(markers), key=len, reverse=True)
    i = 0
    n = len(line)
    quote: Optional[str] = None
    while i < n:
        c = line[i]
        if quote is not None:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in _STRING_CHARS:
            quote = c
            i += 1
            continue
        for m in ordered:
            if line.startswith(m, i):
                return line[:i] + re.sub(r"[^\n]", " ", line[i:])
        i += 1
    return line


def strip_comments(content: str, plugin: LanguagePlugin) -> str:
    """按语言 plugin 的注释规则剥离注释。"""
    if plugin.block_comments:
        content = _strip_block_comments(content, plugin.block_comments)
    if plugin.line_comments:
        content = "\n".join(
            _strip_line_comment(ln, plugin.line_comments)
            for ln in content.split("\n")
        )
    return content


class AssignmentFinder:
    """赋值搜索器: 给定名字与若干目标, 返回命中结果。"""

    def __init__(self, name: str, setters: bool = True, encoding: str = "utf-8",
                 lang: Optional[str] = None, max_size: int = DEFAULT_MAX_SIZE):
        self.variants = NameVariants(name)
        self.setters = setters
        self.encoding = encoding
        self.max_size = max_size
        self._patterns: dict = {}  # plugin -> 编译后的正则
        # --lang 强制指定的 plugin(仅对无法靠扩展名判断的目标生效, 如 stdin)
        self._lang_plugin = get_plugin_by_name(lang) if lang else None

    def _pattern_for(self, plugin: LanguagePlugin) -> Pattern:
        pat = self._patterns.get(plugin)
        if pat is None:
            pat = plugin.build_pattern(self.variants, self.setters)
            self._patterns[plugin] = pat
        return pat

    def _search_text(self, text: str, plugin: LanguagePlugin) -> List[Tuple[int, str, Pattern]]:
        text = strip_comments(text, plugin)
        pat = self._pattern_for(plugin)
        matches: List[Tuple[int, str, Pattern]] = []
        for line_no, line in enumerate(text.split("\n"), 1):
            if pat.search(line):
                matches.append((line_no, line, pat))
        return matches

    def search_file(self, fpath: str) -> Optional[FileResult]:
        ext = os.path.splitext(fpath)[1].lower()
        plugin = get_plugin_by_ext(ext)
        if plugin is None:
            # 未知扩展名: 显式传入的文件仍用兜底 plugin 尝试, 目录遍历则不会收录
            plugin = self._lang_plugin or GENERIC_PLUGIN
        try:
            size = os.path.getsize(fpath)
        except OSError:
            return None
        if size > self.max_size:
            return None
        text = _read_text(fpath, self.encoding)
        if text is None:
            return None
        matches = self._search_text(text, plugin)
        return (fpath, matches) if matches else None

    def search_dir(self, root: str) -> List[FileResult]:
        results: List[FileResult] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in KNOWN_EXTENSIONS:
                    continue
                res = self.search_file(os.path.join(dirpath, fn))
                if res is not None:
                    results.append(res)
        return results

    def search_stdin(self, label: str = "-") -> Optional[FileResult]:
        plugin = self._lang_plugin or GENERIC_PLUGIN
        import sys
        data = sys.stdin.read()
        matches = self._search_text(data, plugin)
        return (label, matches) if matches else None

    def search_targets(self, targets: List[str]) -> List[FileResult]:
        """处理目标列表: 目录递归 / 文件直搜 / '-' 读管道。"""
        results: List[FileResult] = []
        for target in targets:
            if target == "-":
                res = self.search_stdin(target)
                if res is not None:
                    results.append(res)
            elif os.path.isdir(target):
                results.extend(self.search_dir(target))
            else:
                res = self.search_file(target)
                if res is not None:
                    results.append(res)
        return results
