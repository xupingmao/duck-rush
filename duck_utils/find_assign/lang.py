# -*- coding:utf-8 -*-
# @filename duck_utils/find_assign/lang.py
# @description 语言相关的赋值匹配逻辑(与搜索算法解耦)。
#
# 设计要点(满足"语言相关逻辑低耦合"):
#   - 每种语言用一个 LanguagePlugin 描述其"注释写法 / 赋值运算符 / 是否支持
#     setXxx setter"等事实, 引擎只依赖 LanguagePlugin 接口,
#     不关心任何具体语言细节。
#   - 引擎通过扩展名查表得到对应 plugin; 也支持 --lang 直接按名称取 plugin。
#   - 其余语言(未注册)用 GENERIC_PLUGIN 兜底, 仅做最通用的 = / := 匹配。

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from duck_utils.find_assign.name import NameVariants

# re.compile 返回值在 3.6 运行期没有 re.Pattern 这个名字, 用 Any 标注返回值
Pattern = Any


def _operator_alternation(ops: Tuple[str, ...]) -> str:
    """把赋值运算符列表拼成正则 alternation。

    单独的 '=' 必须排除 == / != / <= / >= 的误判(用前后向断言),
    其余复合运算符(+=、:= 等)按字面转义即可。长运算符排在前面优先匹配。
    """
    parts: List[str] = []
    for op in sorted(set(ops), key=len, reverse=True):
        if op == "=":
            parts.append(r"(?<![\=!<>])=(?!\=)")
        else:
            parts.append(re.escape(op))
    return "(?:" + "|".join(parts) + ")"


class LanguagePlugin:
    """一种编程语言的赋值匹配描述(接口 + 默认实现)。"""

    # 语言标识名(供 --lang 使用)
    name: str = "generic"
    # 文件扩展名集合(含点, 小写)
    extensions: Set[str] = set()
    # 行注释标记(按长度降序匹配, 如 // 在 # 之前)
    line_comments: Tuple[str, ...] = ("//", "#")
    # 块注释 (start, end)
    block_comments: Tuple[Tuple[str, str], ...] = (("/*", "*/"),)
    # 该语言的赋值运算符(不含比较/箭头)
    assignment_operators: Tuple[str, ...] = ("=", ":=", "+=", "-=", "*=", "/=",
                                             "%=", "&=", "|=", "^=", "<<=", ">>=")
    # 是否把 setXxx(...) 调用视为赋值
    setter_enabled: bool = True

    def build_pattern(self, variants: NameVariants, setters: bool) -> Pattern:
        """构造匹配"对某名字赋值"的正则(大小写不敏感由引擎加 IGNORECASE)。"""
        id_alt = "|".join(re.escape(v) for v in variants.identifiers)
        # 标识符前后必须是非单词字符, 保证是完整标识符而非子串
        id_re = r"(?<![A-Za-z0-9_])(" + id_alt + r")(?![A-Za-z0-9_])"
        op_re = _operator_alternation(self.assignment_operators)
        assign_re = id_re + r"\s*" + op_re

        parts = [assign_re]
        if setters and self.setter_enabled and variants.setters:
            set_alt = "|".join(re.escape(s) for s in variants.setters)
            set_re = r"(?<![A-Za-z0-9_])(?:" + set_alt + r")\s*\("
            parts.append(set_re)
        return re.compile("(?:" + "|".join(parts) + ")", re.IGNORECASE)


class PythonPlugin(LanguagePlugin):
    name = "python"
    extensions = {".py", ".pyw"}
    line_comments = ("#",)
    block_comments = ()  # 三引号字符串由引擎的字符串感知扫描处理
    assignment_operators = ("=", ":=", "+=", "-=", "*=", "/=", "//=", "%=",
                            "**=", "&=", "|=", "^=", "<<=", ">>=", "@=")
    setter_enabled = True  # Python 也可有 set_xxx / setXxx 风格 setter


class GoPlugin(LanguagePlugin):
    name = "go"
    extensions = {".go"}
    line_comments = ("//",)
    block_comments = (("/*", "*/"),)
    assignment_operators = ("=", ":=", "+=", "-=", "*=", "/=", "%=", "&=",
                            "|=", "^=", "<<=", ">>=", "&^=")
    setter_enabled = True


class JsPlugin(LanguagePlugin):
    name = "javascript"
    extensions = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
    line_comments = ("//",)
    block_comments = (("/*", "*/"),)
    # 排除 => (箭头函数) 以免 name => ... 被误判为赋值
    assignment_operators = ("=", "+=", "-=", "*=", "/=", "**=", "%=", "&=",
                            "|=", "^=", "<<=", ">>=", "&&=")
    setter_enabled = True


class JavaPlugin(LanguagePlugin):
    name = "java"
    extensions = {".java"}
    line_comments = ("//",)
    block_comments = (("/*", "*/"),)
    assignment_operators = ("=", "+=", "-=", "*=", "/=", "%=", "&=", "|=",
                            "^=", "<<=", ">>=")
    setter_enabled = True


class CPlugin(LanguagePlugin):
    name = "c"
    extensions = {".c", ".h"}
    line_comments = ("//",)
    block_comments = (("/*", "*/"),)
    assignment_operators = ("=", "+=", "-=", "*=", "/=", "%=", "&=", "|=",
                            "^=", "<<=", ">>=")
    setter_enabled = True


class CppPlugin(LanguagePlugin):
    name = "cpp"
    extensions = {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".c++", ".h++"}
    line_comments = ("//",)
    block_comments = (("/*", "*/"),)
    assignment_operators = ("=", "+=", "-=", "*=", "/=", "%=", "&=", "|=",
                            "^=", "<<=", ">>=", "->*=")
    setter_enabled = True


class GenericPlugin(LanguagePlugin):
    """兜底: 适用于未注册的语言, 仅做最通用的匹配。"""
    name = "generic"
    extensions = set()
    line_comments = ("//", "#")
    block_comments = (("/*", "*/"),)
    assignment_operators = ("=", ":=", "+=", "-=", "*=", "/=", "%=")
    setter_enabled = True


# 扩展名 -> plugin 注册表(目录遍历 / 文件搜索时按扩展名取)
_LANG_INSTANCES = [
    PythonPlugin(), GoPlugin(), JsPlugin(), JavaPlugin(), CPlugin(), CppPlugin(),
]
EXT_TO_PLUGIN: Dict[str, LanguagePlugin] = {}
for _p in _LANG_INSTANCES:
    for _ext in _p.extensions:
        EXT_TO_PLUGIN[_ext] = _p

# 名称 -> plugin 注册表(供 --lang 使用)
NAME_TO_PLUGIN: Dict[str, LanguagePlugin] = {p.name: p for p in _LANG_INSTANCES}
NAME_TO_PLUGIN[GenericPlugin.name] = GenericPlugin()

GENERIC_PLUGIN = GenericPlugin()
KNOWN_EXTENSIONS = frozenset(EXT_TO_PLUGIN.keys())


def get_plugin_by_ext(ext: str) -> Optional[LanguagePlugin]:
    return EXT_TO_PLUGIN.get(ext.lower())


def get_plugin_by_name(name: str) -> Optional[LanguagePlugin]:
    return NAME_TO_PLUGIN.get(name)


def list_lang_names() -> List[str]:
    return sorted(NAME_TO_PLUGIN.keys())
