# -*- coding:utf-8 -*-
# @filename find_assign_name.py
# @description 命名变体生成: 将一个名字拆词, 派生出 camelCase / PascalCase /
#              snake_case / SCREAMING_SNAKE 等多种形式, 以及 setXXX / set_xxx
#              两种 setter 形式。搜索本身大小写不敏感(引擎用 IGNORECASE), 这里
#              只负责"同一语义在不同命名风格下的等价写法"。
#
# 该模块与具体编程语言无关(高内聚于"命名"), 供 find_assign_engine 与
# find_assign_lang 复用。

import re
from typing import List, Set

# 分隔符: 下划线 / 连字符
_SEP_RE = re.compile(r"[_\-]+")

# 在 camelCase / PascalCase 中插入词边界:
#   - 小写/数字 后跟 大写  (userName -> user|Name)
#   - 连续大写 后跟 大写+小写 (HTTPServer -> HTTP|Server)
_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def split_words(name: str) -> List[str]:
    """把任意命名风格的名字拆成小写单词列表。"""
    name = (name or "").strip()
    if not name:
        return []
    parts = _SEP_RE.split(name)
    words: List[str] = []
    for part in parts:
        if not part:
            continue
        for sub in _BOUNDARY_RE.split(part):
            if sub:
                words.append(sub)
    return words


def _to_snake(words: List[str]) -> str:
    return "_".join(w.lower() for w in words)


def _to_screaming(words: List[str]) -> str:
    return "_".join(w.upper() for w in words)


def _to_camel(words: List[str]) -> str:
    if not words:
        return ""
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


def _to_pascal(words: List[str]) -> str:
    return "".join(w.capitalize() for w in words)


class NameVariants:
    """一个名字在多种命名风格下的等价写法集合。"""

    def __init__(self, raw: str):
        self.raw: str = raw
        self.words: List[str] = split_words(raw)
        self.snake: str = _to_snake(self.words)
        self.screaming: str = _to_screaming(self.words)
        self.camel: str = _to_camel(self.words)
        self.pascal: str = _to_pascal(self.words)

    @property
    def identifiers(self) -> List[str]:
        """直接赋值匹配用的标识符形式(去重)。"""
        out: Set[str] = set()
        for v in (self.raw, self.camel, self.pascal, self.snake, self.screaming):
            if v:
                out.add(v)
        return list(out)

    @property
    def setters(self) -> List[str]:
        """setter 调用形式: setPascal / set_snake。"""
        out: Set[str] = set()
        if self.pascal:
            out.add("set" + self.pascal)
        if self.snake:
            out.add("set_" + self.snake)
        return list(out)

    def __repr__(self) -> str:
        return "NameVariants(raw=%r, variants=%r)" % (self.raw, self.identifiers)
