# encoding=utf-8
"""语法分词工具: 将源代码文本切分为 (类型, 文本) token 序列。

仅负责分词, 不含配色逻辑(配色由调用方决定)。支持:
- 关键字 / 字符串 / 注释 / 数字 / 特殊符号 五类 token, 其余文本以 "text" 类型返回
- 三引号字符串(py/js/go 等)与块注释(/* */、<!-- -->)的跨行状态保持

分词采用逐字符扫描算法(而非正则), 逻辑直观、易维护。跨行状态通过
``state``(一个二元列表 ``[triple_marker, block_marker]``)在多次调用间保持。

典型用法::

    from duck_utils.syntax_util import tokenize, SyntaxTokenizer, Token

    # 一次性分词
    for tok in tokenize("def f(): pass", "python"):
        print(tok.kind, tok.text)

    # 按行流式分词(保持跨行三引号/块注释状态)
    tk = SyntaxTokenizer("python")
    for line in lines:
        for tok in tk.tokenize(line):
            ...
"""

from typing import Dict, Iterator, List, NamedTuple, Optional, Set, Tuple

# 特殊符号集合
SYMBOLS = set("{}()[];,.<>+-*/%=@&|!?~^:")


# 各语言的分词规则。字段说明:
#   keywords      : 关键字集合
#   line_comments : 行注释起始串列表(命中后整行剩余为注释)
#   block         : 块注释 (open, close) 或 None(支持跨行)
#   triple        : 三引号/反引号多行字符串的定界符列表(支持跨行)
LANGUAGES = {
    "python": {
        "keywords": {
            "def", "class", "return", "if", "elif", "else", "for", "while", "break",
            "continue", "pass", "import", "from", "as", "with", "try", "except", "finally",
            "raise", "yield", "lambda", "global", "nonlocal", "assert", "del", "in", "is",
            "not", "and", "or", "None", "True", "False", "async", "await", "print", "self",
        },
        "line_comments": ["#"],
        "block": None,
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
        "line_comments": ["//"],
        "block": ("/*", "*/"),
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
        "line_comments": ["//"],
        "block": ("/*", "*/"),
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
        "line_comments": ["//"],
        "block": ("/*", "*/"),
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
        "line_comments": ["//"],
        "block": ("/*", "*/"),
        "triple": [],
    },
    "go": {
        "keywords": {
            "func", "return", "var", "const", "type", "struct", "interface", "map",
            "chan", "if", "else", "for", "range", "switch", "case", "break", "continue",
            "default", "go", "defer", "select", "package", "import", "nil", "true",
            "false", "string", "int", "bool", "error", "fallthrough",
        },
        "line_comments": ["//"],
        "block": ("/*", "*/"),
        "triple": ["`"],
    },
    "rust": {
        "keywords": {
            "fn", "let", "mut", "const", "static", "return", "if", "else", "for", "while",
            "loop", "match", "break", "continue", "struct", "enum", "trait", "impl",
            "pub", "use", "mod", "where", "as", "in", "self", "Self", "true", "false",
            "Some", "None", "Ok", "Err", "move", "ref", "unsafe", "async", "await",
        },
        "line_comments": ["//"],
        "block": ("/*", "*/"),
        "triple": [],
    },
    "shell": {
        "keywords": {
            "if", "then", "else", "elif", "fi", "for", "while", "do", "done", "case",
            "esac", "function", "return", "exit", "export", "local", "in", "select",
            "until", "break", "continue", "echo", "cd", "set", "unset", "source",
        },
        "line_comments": ["#"],
        "block": None,
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
        "line_comments": ["--", "#"],
        "block": ("/*", "*/"),
        "triple": [],
    },
    "json": {
        "keywords": set(),
        "line_comments": [],
        "block": None,
        "triple": [],
    },
    "yaml": {
        "keywords": {"true", "false", "null", "yes", "no", "on", "off"},
        "line_comments": ["#"],
        "block": None,
        "triple": [],
    },
    "php": {
        "keywords": {
            "function", "return", "class", "public", "private", "protected", "static",
            "echo", "print", "if", "else", "elseif", "for", "foreach", "while", "do",
            "switch", "case", "break", "continue", "new", "try", "catch", "finally",
            "throw", "use", "namespace", "as", "true", "false", "null", "isset", "empty",
        },
        "line_comments": ["//", "#"],
        "block": ("/*", "*/"),
        "triple": [],
    },
    "ruby": {
        "keywords": {
            "def", "class", "module", "return", "if", "elsif", "else", "unless", "for",
            "while", "until", "do", "end", "then", "case", "when", "break", "next",
            "redo", "yield", "self", "nil", "true", "false", "require", "include",
            "attr_accessor", "puts", "print",
        },
        "line_comments": ["#"],
        "block": None,
        "triple": [],
    },
    "lua": {
        "keywords": {
            "function", "end", "return", "if", "then", "else", "elseif", "for", "while",
            "do", "repeat", "until", "break", "local", "nil", "true", "false", "and",
            "or", "not", "in", "print",
        },
        "line_comments": ["--"],
        "block": None,
        "triple": [],
    },
    "html": {
        "keywords": set(),
        "line_comments": [],
        "block": ("<!--", "-->"),
        "triple": [],
    },
    "css": {
        "keywords": {
            "important", "none", "auto", "inherit", "initial", "flex", "block", "inline",
            "grid", "absolute", "relative", "fixed", "static", "true", "false",
        },
        "line_comments": [],
        "block": ("/*", "*/"),
        "triple": [],
    },
}  # type: Dict[str, Dict]

# 默认规则: 不识别语言时, 仍切分字符串/数字/符号, 不做关键字与注释处理
DEFAULT_SPEC = {
    "keywords": set(),
    "line_comments": [],
    "block": None,
    "triple": [],
}  # type: Dict

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


class _ScanState:
    """跨行分词状态: 记录当前未完成的三引号字符串定界符与块注释定界符。

    - ``triple``: 当前处于的三引号/反引号定界符(跨行), 为 None 表示不在多行字符串内
    - ``block``: 当前处于的块注释 (open, close) 元组(跨行), 为 None 表示不在块注释内
    """

    __slots__ = ("triple", "block")

    def __init__(self) -> None:
        self.triple = None  # type: Optional[str]
        self.block = None  # type: Optional[Tuple[str, str]]


def detect_lang(filename: str) -> str:
    """根据扩展名推断语言, 找不到返回 'default'。"""
    if not filename:
        return "default"
    dot = filename.rfind(".")
    if dot == -1:
        return "default"
    ext = filename[dot:].lower()
    return EXT_LANG.get(ext, "default")


def _scan(text: str, spec: Dict, state: _ScanState) -> List[Tuple[str, str]]:
    """逐字符扫描一段文本, 返回 (kind, text) token 列表。

    ``state`` 为 :class:`_ScanState` 实例, 记录当前未完成的三引号字符串定界符与
    块注释定界符。块注释与三引号字符串可跨行; 普通字符串与行注释在行内结束。
    """
    line_comments = spec.get("line_comments") or []  # type: List[str]
    block = spec.get("block")  # type: Optional[Tuple[str, str]]
    triples = spec.get("triple") or []  # type: List[str]
    keywords = spec.get("keywords") or set()  # type: Set[str]

    out = []  # type: List[Tuple[str, str]]
    n = len(text)
    i = 0
    buf = []  # type: List[str]  # 累积尚未确定的普通文本

    def flush():
        if buf:
            out.append(("text", "".join(buf)))
            buf.clear()

    # 1) 处于块注释内部: 在本行内寻找结束标记
    if state.block is not None:
        close = state.block[1]
        j = text.find(close)
        if j == -1:
            out.append(("comment", text))
            return out
        flush()
        out.append(("comment", text[:j + len(close)]))
        i = j + len(close)
        state.block = None

    # 2) 处于三引号字符串内部: 在本行内寻找结束定界符
    if state.triple is not None:
        marker = state.triple
        j = text.find(marker, i)
        if j == -1:
            out.append(("string", text[i:]))
            return out
        flush()
        out.append(("string", text[i:j + len(marker)]))
        i = j + len(marker)
        state.triple = None

    # 3) 普通扫描
    while i < n:
        c = text[i]

        # 块注释 /* */ 或 <!-- -->
        if block is not None and text.startswith(block[0], i):
            j = text.find(block[1], i + len(block[0]))
            if j == -1:
                flush()
                out.append(("comment", text[i:]))
                state.block = block
                return out
            flush()
            out.append(("comment", text[i:j + len(block[1])]))
            i = j + len(block[1])
            continue

        # 行注释(# // -- 等): 命中后整行剩余为注释
        hit_comment = False
        for cm in line_comments:
            if text.startswith(cm, i):
                flush()
                out.append(("comment", text[i:]))
                i = n
                hit_comment = True
                break
        if hit_comment:
            break

        # 字符串 / 三引号字符串
        if c in ('"', "'", '`'):
            flush()
            triple_marker = None  # type: Optional[str]
            for tq in triples:
                if text.startswith(tq, i):
                    triple_marker = tq
                    break
            if triple_marker is not None:
                # 三引号/反引号多行字符串
                j = text.find(triple_marker, i + len(triple_marker))
                if j == -1:
                    out.append(("string", text[i:]))
                    state.triple = triple_marker
                    return out
                out.append(("string", text[i:j + len(triple_marker)]))
                i = j + len(triple_marker)
                continue
            # 普通字符串: 找到匹配的结束引号(支持反斜杠转义)
            delim = c
            k = i + 1
            while k < n:
                if text[k] == '\\':
                    k += 2
                    continue
                if text[k] == delim:
                    k += 1
                    break
                k += 1
            out.append(("string", text[i:k]))
            i = k
            continue

        # 数字(含小数与指数)
        if c.isdigit():
            j = i + 1
            while j < n and (text[j].isdigit() or text[j] == '.'):
                j += 1
            if j < n and text[j] in ('e', 'E'):
                k = j + 1
                if k < n and text[k] in '+-':
                    k += 1
                while k < n and text[k].isdigit():
                    k += 1
                j = k
            flush()
            out.append(("number", text[i:j]))
            i = j
            continue

        # 单词(关键字或标识符)
        if c.isalpha() or c == '_':
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] == '_'):
                j += 1
            word = text[i:j]
            if word in keywords:
                flush()
                out.append(("keyword", word))
            else:
                buf.append(word)
            i = j
            continue

        # 特殊符号
        if c in SYMBOLS:
            flush()
            out.append(("symbol", c))
            i += 1
            continue

        # 其他(空白、换行等)累积为普通文本
        buf.append(c)
        i += 1

    flush()
    return out


def tokenize(text: str, lang: str = "default") -> Iterator[Token]:
    """对一段文本分词, 返回 (kind, text) token 迭代器。

    kind 取值: comment / string / number / keyword / symbol / text。
    三引号字符串与块注释的跨行状态仅在本段 ``text`` 内保持一致; 若需跨多次调用
    保持状态(如按行流式处理), 请使用 :class:`SyntaxTokenizer`。
    """
    spec = LANGUAGES.get(lang, DEFAULT_SPEC)
    state = _ScanState()
    for kind, seg in _scan(text, spec, state):
        yield Token(kind, seg)


class SyntaxTokenizer:
    """按语言维护分词状态的分词器, 适合逐行流式调用并跨行保持三引号/块注释状态。"""

    def __init__(self, lang: str = "default") -> None:
        self.lang = lang
        self._spec = LANGUAGES.get(lang, DEFAULT_SPEC)
        self._state = _ScanState()

    def tokenize(self, text: str) -> Iterator[Token]:
        """对一段文本分词, 返回的 token 迭代器; 跨调用保持三引号/块注释状态。"""
        for kind, seg in _scan(text, self._spec, self._state):
            yield Token(kind, seg)
