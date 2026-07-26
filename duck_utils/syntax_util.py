# encoding=utf-8
"""语法分词工具: 将源代码文本切分为 (类型, 文本) token 序列。

仅负责分词, 不含配色逻辑(配色由调用方决定)。支持:
- 关键字 / 字符串 / 注释 / 数字 / 特殊符号 五类 token, 其余文本以 "text" 类型返回
- 三引号字符串(py/js/go 等)的跨行状态保持

典型用法::

    from duck_utils.syntax_util import tokenize, SyntaxTokenizer, Token

    # 一次性分词
    for tok in tokenize("def f(): pass", "python"):
        print(tok.kind, tok.text)

    # 按行流式分词(保持跨行三引号状态)
    tk = SyntaxTokenizer("python")
    for line in lines:
        for tok in tk.tokenize(line):
            ...
"""

import re
from typing import Dict, Iterator, List, NamedTuple, Optional, Tuple

# 各语言的分词规则: 关键字集合 + 行注释正则(可含 /* */ 块注释) + 三引号字符串标记
LANGUAGES = {
    "python": {
        "keywords": {
            "def", "class", "return", "if", "elif", "else", "for", "while", "break",
            "continue", "pass", "import", "from", "as", "with", "try", "except", "finally",
            "raise", "yield", "lambda", "global", "nonlocal", "assert", "del", "in", "is",
            "not", "and", "or", "None", "True", "False", "async", "await", "print", "self",
        },
        "comment": r"#[^\n]*",
        "triple": ['"""', "'''"],
    },
    "javascript": {
        "keywords": {
            "function", "return", "var", "let", "const", "if", "else", "for", "while",
            "do", "switch", "case", "break", "continue", "new", "class", "extends",
            "super", "this", "typeof", "instanceof", "in", "of", "void", "delete", "try",
            "catch", "finally", "throw", "yield", "async", "await", "import", "export",
            "from", "default", "null", "undefined", "true", "false", "typeof",
        },
        "comment": r"//[^\n]*|/\*.*?\*/",
        "triple": ["`"],
    },
    "typescript": {
        "keywords": {
            "function", "return", "var", "let", "const", "if", "else", "for", "while",
            "do", "switch", "case", "break", "continue", "new", "class", "extends",
            "implements", "interface", "type", "enum", "public", "private", "protected",
            "readonly", "static", "this", "typeof", "instanceof", "in", "of", "void",
            "delete", "try", "catch", "finally", "throw", "yield", "async", "await",
            "import", "export", "from", "default", "namespace", "as", "null", "undefined",
            "true", "false",
        },
        "comment": r"//[^\n]*|/\*.*?\*/",
        "triple": ["`"],
    },
    "c": {
        "keywords": {
            "int", "char", "float", "double", "long", "short", "unsigned", "signed",
            "void", "struct", "union", "enum", "typedef", "static", "const", "return",
            "if", "else", "for", "while", "do", "switch", "case", "break", "continue",
            "default", "goto", "sizeof", "extern", "register", "volatile", "auto", "new",
            "delete", "class", "public", "private", "protected", "virtual", "template",
            "namespace", "using", "this", "true", "false", "bool", "NULL", "nullptr",
        },
        "comment": r"//[^\n]*|/\*.*?\*/",
        "triple": [],
    },
    "java": {
        "keywords": {
            "int", "char", "float", "double", "long", "short", "byte", "boolean", "void",
            "class", "interface", "enum", "public", "private", "protected", "static",
            "final", "abstract", "return", "if", "else", "for", "while", "do", "switch",
            "case", "break", "continue", "default", "new", "this", "super", "extends",
            "implements", "import", "package", "try", "catch", "finally", "throw", "throws",
            "true", "false", "null", "instanceof", "synchronized", "volatile", "transient",
        },
        "comment": r"//[^\n]*|/\*.*?\*/",
        "triple": [],
    },
    "go": {
        "keywords": {
            "func", "return", "var", "const", "type", "struct", "interface", "map",
            "chan", "if", "else", "for", "range", "switch", "case", "break", "continue",
            "default", "go", "defer", "select", "package", "import", "nil", "true",
            "false", "string", "int", "bool", "error", "fallthrough",
        },
        "comment": r"//[^\n]*|/\*.*?\*/",
        "triple": ["`"],
    },
    "rust": {
        "keywords": {
            "fn", "let", "mut", "const", "static", "return", "if", "else", "for", "while",
            "loop", "match", "break", "continue", "struct", "enum", "trait", "impl",
            "pub", "use", "mod", "where", "as", "in", "self", "Self", "true", "false",
            "Some", "None", "Ok", "Err", "move", "ref", "unsafe", "async", "await",
        },
        "comment": r"//[^\n]*|/\*.*?\*/",
        "triple": [],
    },
    "shell": {
        "keywords": {
            "if", "then", "else", "elif", "fi", "for", "while", "do", "done", "case",
            "esac", "function", "return", "exit", "export", "local", "in", "select",
            "until", "break", "continue", "echo", "cd", "set", "unset", "source",
        },
        "comment": r"#[^\n]*",
        "triple": [],
    },
    "sql": {
        "keywords": {
            "select", "from", "where", "insert", "update", "delete", "create", "table",
            "drop", "alter", "index", "view", "join", "inner", "left", "right", "outer",
            "on", "group", "by", "order", "having", "limit", "offset", "as", "and", "or",
            "not", "null", "is", "in", "exists", "between", "like", "distinct", "count",
            "sum", "avg", "min", "max", "into", "values", "set", "begin", "commit", "rollback",
        },
        "comment": r"--[^\n]*|#[^\n]*|/\*.*?\*/",
        "triple": [],
    },
    "json": {
        "keywords": set(),
        "comment": None,
        "triple": [],
    },
    "yaml": {
        "keywords": {"true", "false", "null", "yes", "no", "on", "off"},
        "comment": r"#[^\n]*",
        "triple": [],
    },
    "php": {
        "keywords": {
            "function", "return", "class", "public", "private", "protected", "static",
            "echo", "print", "if", "else", "elseif", "for", "foreach", "while", "do",
            "switch", "case", "break", "continue", "new", "try", "catch", "finally",
            "throw", "use", "namespace", "as", "true", "false", "null", "isset", "empty",
        },
        "comment": r"#[^\n]*|//[^\n]*|/\*.*?\*/",
        "triple": [],
    },
    "ruby": {
        "keywords": {
            "def", "class", "module", "return", "if", "elsif", "else", "unless", "for",
            "while", "until", "do", "end", "then", "case", "when", "break", "next",
            "redo", "yield", "self", "nil", "true", "false", "require", "include",
            "attr_accessor", "puts", "print",
        },
        "comment": r"#[^\n]*",
        "triple": [],
    },
    "lua": {
        "keywords": {
            "function", "end", "return", "if", "then", "else", "elseif", "for", "while",
            "do", "repeat", "until", "break", "local", "nil", "true", "false", "and",
            "or", "not", "in", "print",
        },
        "comment": r"--[^\n]*",
        "triple": [],
    },
    "html": {
        "keywords": set(),
        "comment": r"<!--.*?-->",
        "triple": [],
    },
    "css": {
        "keywords": {
            "important", "none", "auto", "inherit", "initial", "flex", "block", "inline",
            "grid", "absolute", "relative", "fixed", "static", "true", "false",
        },
        "comment": r"/\*.*?\*/",
        "triple": [],
    },
}  # type: Dict[str, Dict]

# 默认规则: 不识别语言时, 仍切分字符串/数字/符号, 不做关键字与注释处理
DEFAULT_SPEC = {"keywords": set(), "comment": None, "triple": []}  # type: Dict

# 扩展名 -> 语言
EXT_LANG = {
    ".py": "python", ".pyw": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".c": "c", ".h": "c", ".cpp": "c", ".cc": "c", ".cxx": "c", ".hpp": "c",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".sql": "sql",
    ".json": "json",
    ".yml": "yaml", ".yaml": "yaml",
    ".php": "php",
    ".rb": "ruby",
    ".lua": "lua",
    ".html": "html", ".htm": "html",
    ".css": "css",
}  # type: Dict[str, str]

# token 类型集合
TOKEN_KINDS = {"comment", "string", "number", "keyword", "symbol", "text"}


class Token(NamedTuple):
    """分词结果: kind 为 token 类型, text 为原始文本切片。"""
    kind: str
    text: str


def detect_lang(filename: str) -> str:
    """根据扩展名推断语言, 找不到返回 'default'。"""
    if not filename:
        return "default"
    dot = filename.rfind(".")
    if dot == -1:
        return "default"
    ext = filename[dot:].lower()
    return EXT_LANG.get(ext, "default")


def build_tokenizer(lang: str) -> "re.Pattern":
    """为指定语言构造分词正则(具名分组: comment/string/number/keyword/symbol)。"""
    spec = LANGUAGES.get(lang, DEFAULT_SPEC)
    patterns = []  # type: List[str]
    comment = spec.get("comment")
    if comment:
        patterns.append(r"(?P<comment>%s)" % comment)
    # 字符串: 单双反引号, 支持转义
    patterns.append(r"(?P<string>\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)")
    # 数字
    patterns.append(r"(?P<number>\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)")
    keywords = spec.get("keywords") or set()
    if keywords:
        # 长关键字优先, 避免子串抢占
        kw = "|".join(re.escape(k) for k in sorted(keywords, key=len, reverse=True))
        patterns.append(r"(?P<keyword>\b(?:%s)\b)" % kw)
    # 特殊符号
    patterns.append(r"(?P<symbol>[{}()\[\];,.<>+\-*/%=@&|!?~^:])")
    return re.compile("|".join(patterns))


def _scan_normal(text: str, tok: "re.Pattern") -> Iterator[Tuple[str, str]]:
    """对普通(非三引号字符串)片段做分词, 未被匹配的间隙以 'text' 类型返回。"""
    pos = 0
    for m in tok.finditer(text):
        s, e = m.span()
        if s > pos:
            yield ("text", text[pos:s])
        kind = m.lastgroup
        assert kind is not None
        yield (kind, m.group())
        pos = e
    if pos < len(text):
        yield ("text", text[pos:])


def _scan(text: str, tok: "re.Pattern", triples: List[str],
          state: List[Optional[str]]) -> Iterator[Tuple[str, str]]:
    """对一段文本分词, 处理三引号字符串的跨行状态(state 为单元素列表, 由调用方持有)。"""
    pos = 0

    # 仍处于三引号字符串内部: 找结束标记
    if state[0] is not None:
        marker = state[0]
        idx = text.find(marker, pos)
        if idx == -1:
            yield ("string", text[pos:])
            return
        yield ("string", text[pos:idx + len(marker)])
        pos = idx + len(marker)
        state[0] = None

    # 扫描同行内的三引号字符串, 进入/退出状态
    while triples:
        best = None  # type: Optional[Tuple[int, str]]
        for tq in triples:
            i = text.find(tq, pos)
            if i != -1 and (best is None or i < best[0]):
                best = (i, tq)
        if best is None:
            break
        i, tq = best
        for seg in _scan_normal(text[pos:i], tok):
            yield seg
        j = text.find(tq, i + len(tq))
        if j == -1:
            yield ("string", text[i:])
            state[0] = tq
            return
        yield ("string", text[i:j + len(tq)])
        pos = j + len(tq)

    for seg in _scan_normal(text[pos:], tok):
        yield seg


def tokenize(text: str, lang: str = "default") -> Iterator[Token]:
    """对一段文本分词, 返回 (kind, text) token 迭代器。

    kind 取值: comment / string / number / keyword / symbol / text。
    三引号字符串的跨行状态仅在本段 ``text`` 内保持一致; 若需跨多次调用保持
    状态(如按行流式处理), 请使用 :class:`SyntaxTokenizer`。
    """
    tok = build_tokenizer(lang)
    triples = LANGUAGES.get(lang, DEFAULT_SPEC).get("triple", [])
    state = [None]  # type: List[Optional[str]]
    for kind, seg in _scan(text, tok, triples, state):
        yield Token(kind, seg)


class SyntaxTokenizer:
    """按语言维护分词状态的分词器, 适合逐行流式调用并跨行保持三引号字符串状态。"""

    def __init__(self, lang: str = "default") -> None:
        self.lang = lang
        self._tok = build_tokenizer(lang)
        self._triples = LANGUAGES.get(lang, DEFAULT_SPEC).get("triple", [])
        self._state = [None]  # type: List[Optional[str]]

    def tokenize(self, text: str) -> Iterator[Token]:
        """对一段文本分词, 返回的 token 迭代器; 跨调用保持三引号字符串状态。"""
        for kind, seg in _scan(text, self._tok, self._triples, self._state):
            yield Token(kind, seg)
