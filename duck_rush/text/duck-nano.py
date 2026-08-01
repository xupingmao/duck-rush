# -*- coding: utf-8 -*-
"""
duck-nano —— 终端文本编辑器（复刻 nano 的基础功能，基于 prompt_toolkit）。

特性：
- 打开已有文件或新建文件；保存时保留原编码（chardet 自动探测）与原换行符（CRLF / LF / CR）
- 语法高亮（复用 duck_utils.syntax_util，支持 python / js / go / java / c / shell 等）
- nano 风格快捷键，顶部标题栏 + 底部状态行 + 两行快捷键提示栏

快捷键:
  ^G 帮助      ^O 写出      ^W 搜索      ^K 剪切当前行    ^C 显示位置
  ^X 退出      ^S 保存      ^\\ 替换      ^U 粘贴          ^_ 跳转到行
  ^Y / PageUp 上一页        ^V / PageDown 下一页          ^A / ^E 行首 / 行尾

用法:
  duck-nano [文件] [--encoding ENC] [-l] [--tabsize N] [--tabstospaces] [--no-color] [-h]

说明:
  文件不存在时以空白缓冲区打开，直到 ^O / ^S 保存时才真正创建。
  ^W 搜索：直接回车表示重复上次搜索；搜到文件尾后自动从开头继续。
  ^\\ 替换为「全部替换」（先输入查找词，再输入替换词），完成后状态行报告替换处数。
  提示行内：回车确认，^C 取消。
"""
import argparse
import codecs
import logging
import os
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.key_binding.bindings.scroll import scroll_page_down, scroll_page_up
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.margins import NumberedMargin
from prompt_toolkit.layout.processors import TabsProcessor
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style

from duck_utils.syntax_util import SyntaxTokenizer, detect_lang

DEFAULT_ENCODING = "utf-8"

# BOM -> codec 名。BOM 的读写完全交给 codec 名负责（解码自动去掉、编码自动写回），
# 因此绝不手工剥离 \ufeff —— 那样保存时 BOM 会丢失或重复。
# 注意 utf-32 的 BOM 以 utf-16 的 BOM 开头，必须先匹配 utf-32。
# utf-16 / utf-32 在编码时写的是本机字节序的 BOM，故大端文件另存后会变成本机字节序。
_BOM_CODECS: List[Tuple[bytes, str]] = [
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
]


class FileText(NamedTuple):
    """文件内容及其原始编码 / 换行符，用于保存时原样写回。"""

    text: str       # 换行符已统一归一化为 \n
    encoding: str   # 实际用于解码的 codec 名（保存时复用）
    newline: str    # 原始换行符： "\r\n" | "\n" | "\r"
    exists: bool    # 文件是否已存在（新建文件为 False）


# ------------------------------------------------------------------ #
# 文件编解码：保留原编码与原换行符
# ------------------------------------------------------------------ #
def detect_newline(text: str) -> str:
    """按出现次数判断文本的主要换行符；没有换行符时返回平台默认。"""
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    if crlf > 0 and crlf >= lf and crlf >= cr:
        return "\r\n"
    if lf > 0 and lf >= cr:
        return "\n"
    if cr > 0:
        return "\r"
    return os.linesep


def _codec_by_bom(data: bytes) -> Optional[str]:
    """按 BOM 判断 codec 名，无 BOM 返回 None。"""
    for bom, name in _BOM_CODECS:
        if data.startswith(bom):
            return name
    return None


def _detect_encoding(data: bytes) -> Optional[str]:
    """用 chardet 探测编码；chardet 缺失或探测失败时返回 None。"""
    try:
        import chardet
    except ImportError:
        return None
    # chardet 内部会在 DEBUG 级别打印大量探测日志，打开文件时刷屏，统一压到 WARNING
    logging.getLogger("chardet").setLevel(logging.WARNING)
    try:
        result = chardet.detect(data)
    except Exception:  # noqa: 探测失败不应影响打开文件
        return None
    if not result:
        return None
    encoding = result.get("encoding")
    return encoding if isinstance(encoding, str) else None


def decode_bytes(data: bytes, encoding: Optional[str] = None) -> Tuple[str, str]:
    """解码文件字节，返回 (文本, 实际使用的 codec 名)。

    尝试顺序：显式指定的编码 -> BOM -> utf-8 -> chardet 探测 -> utf-8(replace) 兜底。
    """
    candidates: List[str] = []
    if encoding:
        candidates.append(encoding)
    bom_codec = _codec_by_bom(data)
    if bom_codec:
        candidates.append(bom_codec)
    candidates.append("utf-8")
    detected = _detect_encoding(data)
    if detected:
        candidates.append(detected)

    for name in candidates:
        try:
            return data.decode(name), name
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace"), "utf-8"


def load_file(path: str, encoding: Optional[str] = None) -> FileText:
    """读取文件，返回归一化为 \\n 的文本及其原编码 / 换行符。

    文件不存在时返回空缓冲区（exists=False），保存时才真正创建。
    """
    if not path or not os.path.isfile(path):
        return FileText("", encoding or DEFAULT_ENCODING, os.linesep, False)
    with open(path, "rb") as fp:
        data = fp.read()
    raw, enc = decode_bytes(data, encoding)
    newline = detect_newline(raw)
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    return FileText(text, enc, newline, True)


def encode_text(text: str, doc: FileText) -> bytes:
    """把编辑器内的文本（\\n 换行）转回原换行符，并按原编码编码。"""
    if doc.newline != "\n":
        text = text.replace("\n", doc.newline)
    return text.encode(doc.encoding)


def save_file(path: str, text: str, doc: FileText) -> int:
    """保存文件，返回写入的字节数。

    编码失败时抛出 UnicodeEncodeError，由调用方提示用户，绝不静默改用其他编码。
    """
    data = encode_text(text, doc)
    with open(path, "wb") as fp:
        fp.write(data)
    return len(data)


# ------------------------------------------------------------------ #
# 纯文本操作（与界面无关，便于单测）
# ------------------------------------------------------------------ #
def find_next(text: str, term: str, start: int, ignore_case: bool = True) -> Optional[int]:
    """从 start 开始查找 term，搜到文件尾后从开头环绕；找不到返回 None。"""
    if not term:
        return None
    haystack = text.lower() if ignore_case else text
    needle = term.lower() if ignore_case else term
    pos = haystack.find(needle, max(0, start))
    if pos >= 0:
        return pos
    pos = haystack.find(needle)
    return pos if pos >= 0 else None


def replace_all(text: str, old: str, new: str,
                ignore_case: bool = True) -> Tuple[str, int]:
    """全部替换，返回 (新文本, 替换处数)。"""
    if not old:
        return text, 0
    if not ignore_case:
        return text.replace(old, new), text.count(old)

    # 大小写不敏感：按小写文本定位，拼接时保留未匹配部分的原始大小写
    haystack = text.lower()
    needle = old.lower()
    parts: List[str] = []
    count = 0
    index = 0
    while True:
        hit = haystack.find(needle, index)
        if hit < 0:
            break
        parts.append(text[index:hit])
        parts.append(new)
        index = hit + len(needle)
        count += 1
    parts.append(text[index:])
    return "".join(parts), count


def cut_line(text: str, cursor: int) -> Tuple[str, int, str]:
    """剪切光标所在行，返回 (新文本, 新光标位置, 被剪切的内容)。

    仿 nano 的 ^K：整行连同行尾换行符一起移除；末行没有换行符时只移除行内容。
    """
    cursor = max(0, min(cursor, len(text)))
    start = text.rfind("\n", 0, cursor) + 1
    end = text.find("\n", start)
    end = len(text) if end < 0 else end + 1
    return text[:start] + text[end:], start, text[start:end]


def line_col(text: str, cursor: int) -> Tuple[int, int]:
    """返回光标所在的行号与列号（均从 1 开始）。"""
    cursor = max(0, min(cursor, len(text)))
    line = text.count("\n", 0, cursor) + 1
    col = cursor - (text.rfind("\n", 0, cursor) + 1) + 1
    return line, col


def line_start_offset(text: str, lineno: int) -> int:
    """返回第 lineno 行（从 1 开始）的起始偏移量，行号越界时钳制到首尾行。"""
    lines = text.split("\n")
    lineno = max(1, min(lineno, len(lines)))
    return sum(len(line) + 1 for line in lines[:lineno - 1])


# ------------------------------------------------------------------ #
# 语法高亮
# ------------------------------------------------------------------ #
_TOKEN_STYLE = {
    "comment": "class:token.comment",
    "string": "class:token.string",
    "number": "class:token.number",
    "keyword": "class:token.keyword",
    "symbol": "class:token.symbol",
    "text": "",
}


class DuckLexer(Lexer):
    """基于 duck_utils.syntax_util 的语法高亮器（惰性按行分词）。

    prompt_toolkit 只对需要渲染的行调用 get_line(i)，且可能乱序取行；而
    SyntaxTokenizer 必须顺序推进才能维持三引号 / 块注释的跨行状态。因此这里
    维护「已分词到第几行」的游标与行缓存：取第 i 行时若 i 超过游标就顺序推进
    到 i 并缓存沿途结果，否则直接命中缓存。这样打开大文件时首帧只需分词到
    可见区末行。

    lex_document 的返回值已由 BufferControl 按 (document.text, invalidation_hash)
    缓存，故这里无需再按文本内容做一层缓存。
    """

    def __init__(self, lang: str = "default") -> None:
        self.lang = lang

    def lex_document(self, document: Document) -> Callable[[int], StyleAndTextTuples]:
        lines = document.lines
        tokenizer = SyntaxTokenizer(self.lang)
        cache: Dict[int, StyleAndTextTuples] = {}
        lexed_upto = -1

        def get_line(lineno: int) -> StyleAndTextTuples:
            nonlocal lexed_upto
            if lineno < 0 or lineno >= len(lines):
                return []
            while lexed_upto < lineno:
                lexed_upto += 1
                fragments: StyleAndTextTuples = []
                for token in tokenizer.tokenize(lines[lexed_upto]):
                    if token.text:
                        fragments.append((_TOKEN_STYLE.get(token.kind, ""), token.text))
                cache[lexed_upto] = fragments
            return cache.get(lineno, [])

        return get_line


_STYLE = Style.from_dict(
    {
        "titlebar": "reverse bold",
        "statusbar": "ansicyan",
        "statusbar.error": "ansired bold",
        "promptlabel": "ansiyellow bold",
        "keybar.key": "reverse",
        "token.comment": "ansibrightblack",
        "token.string": "ansigreen",
        "token.number": "ansimagenta",
        "token.keyword": "ansiblue bold",
        "token.symbol": "ansiyellow",
    }
)


# ------------------------------------------------------------------ #
# 编辑器
# ------------------------------------------------------------------ #
MODE_EDIT = "edit"
MODE_PROMPT = "prompt"
MODE_CONFIRM = "confirm"

PROMPT_SAVE = "save"
PROMPT_SEARCH = "search"
PROMPT_REPLACE_FROM = "replace_from"
PROMPT_REPLACE_TO = "replace_to"
PROMPT_GOTO = "goto"

_PROMPT_LABELS = {
    PROMPT_SAVE: "写出文件: ",
    PROMPT_SEARCH: "搜索: ",
    PROMPT_REPLACE_FROM: "查找: ",
    PROMPT_REPLACE_TO: "替换为: ",
    PROMPT_GOTO: "跳转到行: ",
}

# 底部两行快捷键提示（每行若干 (键, 说明)）
_KEY_HINTS = [
    [("^G", "帮助"), ("^O", "写出"), ("^W", "搜索"), ("^K", "剪切行"), ("^C", "位置")],
    [("^X", "退出"), ("^S", "保存"), ("^\\", "替换"), ("^U", "粘贴"), ("^_", "跳转")],
]

_HELP_LINES = [
    "duck-nano 快捷键 —— 按任意键返回编辑",
    "",
    "  ^G   显示本帮助",
    "  ^O   写出（提示文件名，回车确认）",
    "  ^S   按当前文件名直接保存",
    "  ^X   退出（有未保存修改时会先询问）",
    "  ^W   搜索（直接回车重复上次搜索，搜到文件尾自动从开头继续）",
    "  ^\\   替换（先输入查找词，再输入替换词，全部替换）",
    "  ^K   剪切当前行（在同一位置连续按可累积）",
    "  ^U   粘贴剪切缓冲区",
    "  ^C   显示光标所在行 / 列",
    "  ^_   跳转到指定行",
    "  ^Y / PageUp     上一页",
    "  ^V / PageDown   下一页",
    "  ^A / ^E         行首 / 行尾",
    "",
    "  提示行内：回车确认，^C 取消",
]


@dataclass
class EditorOptions:
    """duck-nano 的运行参数（集中成一个对象，避免构造器出现过多位置参数）。"""

    encoding: Optional[str] = None
    line_numbers: bool = False
    tab_size: int = 4
    tabs_to_spaces: bool = False
    color: bool = True


class DuckEditApp:
    """nano 风格的全屏文本编辑器。"""

    def __init__(self, path: str, options: Optional[EditorOptions] = None) -> None:
        self.options = options or EditorOptions()
        self.path = path
        self.doc = load_file(path, self.options.encoding)
        self.buffer = Buffer(document=Document(self.doc.text, 0), multiline=True)
        self.prompt_buffer = Buffer(multiline=False)
        self.saved_text = self.doc.text

        self.mode = MODE_EDIT
        self.prompt_kind = ""
        self.show_help = False
        self.confirm_question = ""
        self.status = self._initial_status()
        self.status_error = False

        self.cut_buffer = ""
        # 上次 ^K 结束时的光标位置：与当前位置相同则视为连续剪切，累积到同一缓冲区
        self.cut_at: Optional[int] = None
        self.search_term = ""
        self.replace_from = ""
        self.exit_after_save = False

        self.editor_window = self._build_editor_window()
        self.help_window = Window(FormattedTextControl(self._help_text, focusable=True))
        self.prompt_window = Window(BufferControl(buffer=self.prompt_buffer), height=1)
        self._app: Application = Application(
            layout=self._build_layout(),
            key_bindings=self._build_bindings(),
            style=_STYLE,
            full_screen=True,
            mouse_support=False,
        )

    def _initial_status(self) -> str:
        if not self.path:
            return "[ 新缓冲区 ]"
        if not self.doc.exists:
            return "[ 新文件 ]"
        return "[ 已读取 %d 行 · %s · %s ]" % (
            self.doc.text.count("\n") + 1,
            self.doc.encoding,
            _newline_label(self.doc.newline),
        )

    # ------------------------------------------------------------------ #
    # 布局
    # ------------------------------------------------------------------ #
    def _build_editor_window(self) -> Window:
        lexer = DuckLexer(detect_lang(self.path)) if self.options.color else None
        control = BufferControl(
            buffer=self.buffer,
            lexer=lexer,
            # 默认的 processors 不含 TabsProcessor，缺了它文本里的 \t 会显示成 ^I，
            # 且光标列会算错
            input_processors=[
                TabsProcessor(tabstop=self.options.tab_size, char1=" ", char2=" ")
            ],
        )
        margins = [NumberedMargin()] if self.options.line_numbers else []
        return Window(control, left_margins=margins, wrap_lines=False)

    def _build_layout(self) -> Layout:
        body = HSplit(
            [
                Window(FormattedTextControl(self._title_text), height=1,
                       style="class:titlebar"),
                ConditionalContainer(
                    self.editor_window,
                    filter=Condition(lambda: not self.show_help),
                ),
                ConditionalContainer(
                    self.help_window,
                    filter=Condition(lambda: self.show_help),
                ),
                ConditionalContainer(
                    VSplit(
                        [
                            Window(FormattedTextControl(self._prompt_label), height=1,
                                   dont_extend_width=True, style="class:promptlabel"),
                            self.prompt_window,
                        ],
                        height=1,
                    ),
                    filter=Condition(lambda: self.mode == MODE_PROMPT),
                ),
                Window(FormattedTextControl(self._status_text), height=1),
                Window(FormattedTextControl(self._keybar_text), height=2),
            ]
        )
        return Layout(body, focused_element=self.editor_window)

    def _title_text(self) -> StyleAndTextTuples:
        name = self.path or "新缓冲区"
        flag = "  [已修改]" if self._is_dirty() else ""
        return [("", " duck-nano   %s%s" % (name, flag))]

    def _help_text(self) -> StyleAndTextTuples:
        return [("", "\n".join(_HELP_LINES))]

    def _prompt_label(self) -> StyleAndTextTuples:
        return [("", _PROMPT_LABELS.get(self.prompt_kind, ""))]

    def _status_text(self) -> StyleAndTextTuples:
        if self.mode == MODE_CONFIRM:
            return [("class:statusbar.error", self.confirm_question)]
        style = "class:statusbar.error" if self.status_error else "class:statusbar"
        return [(style, self.status)]

    def _keybar_text(self) -> StyleAndTextTuples:
        fragments: StyleAndTextTuples = []
        for row_index, row in enumerate(_KEY_HINTS):
            if row_index:
                fragments.append(("", "\n"))
            for key, label in row:
                fragments.append(("class:keybar.key", key))
                fragments.append(("", " " + label + "   "))
        return fragments

    # ------------------------------------------------------------------ #
    # 状态
    # ------------------------------------------------------------------ #
    def _is_dirty(self) -> bool:
        return self.buffer.text != self.saved_text

    def _set_status(self, message: str, error: bool = False) -> None:
        self.status = message
        self.status_error = error

    # ------------------------------------------------------------------ #
    # 提示行（保存文件名 / 搜索 / 替换 / 跳转）
    # ------------------------------------------------------------------ #
    def _open_prompt(self, kind: str, default: str = "") -> None:
        self.prompt_kind = kind
        self.prompt_buffer.document = Document(default, len(default))
        # 先切模式让提示行可见，再移动焦点：焦点不能停在隐藏的容器里
        self.mode = MODE_PROMPT
        self._app.layout.focus(self.prompt_window)

    def _close_prompt(self) -> None:
        # 与打开时相反：先把焦点交回正文，再隐藏提示行
        self._app.layout.focus(self.editor_window)
        self.mode = MODE_EDIT
        self.prompt_kind = ""

    def _cancel_prompt(self) -> None:
        self.exit_after_save = False
        self._close_prompt()
        self._set_status("[ 已取消 ]")

    def _submit_prompt(self) -> None:
        kind = self.prompt_kind
        value = self.prompt_buffer.text
        self._close_prompt()
        if kind == PROMPT_SAVE:
            self._save_and_maybe_exit(value.strip())
        elif kind == PROMPT_SEARCH:
            self._search(value or self.search_term)
        elif kind == PROMPT_REPLACE_FROM:
            if not value:
                self._set_status("未输入查找内容", error=True)
                return
            self.replace_from = value
            self._open_prompt(PROMPT_REPLACE_TO)
        elif kind == PROMPT_REPLACE_TO:
            self._replace_all(self.replace_from, value)
        elif kind == PROMPT_GOTO:
            self._goto_line(value)

    # ------------------------------------------------------------------ #
    # 各项功能
    # ------------------------------------------------------------------ #
    def _save_and_maybe_exit(self, path: str) -> None:
        if self._do_save(path) and self.exit_after_save:
            self._app.exit()
            return
        self.exit_after_save = False

    def _do_save(self, path: str) -> bool:
        if not path:
            self._set_status("未指定文件名，保存已取消", error=True)
            return False
        text = self.buffer.text
        try:
            size = save_file(path, text, self.doc)
        except UnicodeEncodeError:
            self._set_status(
                "保存失败: 内容含 %s 无法表示的字符（可用 --encoding utf-8 重新打开）"
                % self.doc.encoding,
                error=True,
            )
            return False
        except OSError as e:
            self._set_status("保存失败: %s" % e, error=True)
            return False
        self.path = path
        self.saved_text = text
        self.doc = self.doc._replace(exists=True)
        self._set_status("[ 已写入 %d 行 · %d 字节 ]" % (text.count("\n") + 1, size))
        return True

    def _search(self, term: str) -> None:
        if not term:
            self._set_status("未输入搜索内容", error=True)
            return
        self.search_term = term
        pos = find_next(self.buffer.text, term, self.buffer.cursor_position + 1)
        if pos is None:
            self._set_status('未找到 "%s"' % term, error=True)
            return
        self.buffer.cursor_position = pos
        line, col = line_col(self.buffer.text, pos)
        self._set_status('找到 "%s"  第 %d 行 第 %d 列' % (term, line, col))

    def _replace_all(self, old: str, new: str) -> None:
        text, count = replace_all(self.buffer.text, old, new)
        if not count:
            self._set_status('未找到 "%s"' % old, error=True)
            return
        cursor = min(self.buffer.cursor_position, len(text))
        self.buffer.document = Document(text, cursor)
        self._set_status("已替换 %d 处" % count)

    def _goto_line(self, value: str) -> None:
        try:
            lineno = int(value.strip())
        except ValueError:
            self._set_status("行号无效: %s" % value, error=True)
            return
        self.buffer.cursor_position = line_start_offset(self.buffer.text, lineno)
        self._set_status("已跳转到第 %d 行" % line_col(self.buffer.text,
                                                       self.buffer.cursor_position)[0])

    def _cut_current_line(self) -> None:
        cursor = self.buffer.cursor_position
        text, new_cursor, cut = cut_line(self.buffer.text, cursor)
        # 连续在同一位置按 ^K 时累积到同一剪切缓冲区（nano 行为）
        self.cut_buffer = self.cut_buffer + cut if self.cut_at == cursor else cut
        self.buffer.document = Document(text, new_cursor)
        self.cut_at = new_cursor
        self._set_status("[ 已剪切 1 行 ]")

    def _paste(self) -> None:
        if not self.cut_buffer:
            self._set_status("剪切缓冲区为空", error=True)
            return
        self.buffer.insert_text(self.cut_buffer)
        self.cut_at = None

    def _show_position(self) -> None:
        text = self.buffer.text
        line, col = line_col(text, self.buffer.cursor_position)
        self._set_status(
            "第 %d/%d 行  第 %d 列  第 %d/%d 字符"
            % (line, text.count("\n") + 1, col, self.buffer.cursor_position, len(text))
        )

    def _toggle_help(self) -> None:
        if self.show_help:
            # 先把焦点交回正文，再隐藏帮助
            self._app.layout.focus(self.editor_window)
            self.show_help = False
        else:
            # 先显示帮助，再把焦点移过去
            self.show_help = True
            self._app.layout.focus(self.help_window)

    def _request_exit(self) -> None:
        if not self._is_dirty():
            self._app.exit()
            return
        self.mode = MODE_CONFIRM
        self.confirm_question = "缓冲区已修改，是否保存？  Y 保存   N 放弃   ^C 取消"

    def _confirm_save(self) -> None:
        self.mode = MODE_EDIT
        self.exit_after_save = True
        self._open_prompt(PROMPT_SAVE, self.path)

    def _confirm_discard(self) -> None:
        self.mode = MODE_EDIT
        self._app.exit()

    def _confirm_cancel(self) -> None:
        self.mode = MODE_EDIT
        self._set_status("[ 已取消 ]")

    # ------------------------------------------------------------------ #
    # 按键绑定
    # ------------------------------------------------------------------ #
    def _build_bindings(self) -> KeyBindings:
        bindings = KeyBindings()
        is_edit = Condition(lambda: self.mode == MODE_EDIT and not self.show_help)
        is_prompt = Condition(lambda: self.mode == MODE_PROMPT)
        is_confirm = Condition(lambda: self.mode == MODE_CONFIRM)
        is_help = Condition(lambda: self.show_help)

        # ---- 帮助：显示时任意键返回 ----
        @bindings.add("c-g", filter=is_edit)
        def _help(event: KeyPressEvent) -> None:
            self._toggle_help()

        @bindings.add(Keys.Any, filter=is_help, eager=True)
        @bindings.add("c-g", filter=is_help, eager=True)
        def _help_close(event: KeyPressEvent) -> None:
            self._toggle_help()

        # ---- 退出 / 保存 ----
        # c-x 必须 eager：emacs 默认绑定里有 "c-x <第二个键>" 的前缀绑定，
        # 不加 eager 的话单独按 c-x 会一直等待第二个键
        @bindings.add("c-x", filter=is_edit, eager=True)
        def _exit(event: KeyPressEvent) -> None:
            self._request_exit()

        @bindings.add("c-o", filter=is_edit)
        def _write_out(event: KeyPressEvent) -> None:
            self._open_prompt(PROMPT_SAVE, self.path)

        @bindings.add("c-s", filter=is_edit)
        def _save(event: KeyPressEvent) -> None:
            if self.path:
                self._do_save(self.path)
            else:
                self._open_prompt(PROMPT_SAVE)

        # ---- 搜索 / 替换 / 跳转 ----
        @bindings.add("c-w", filter=is_edit)
        def _search_key(event: KeyPressEvent) -> None:
            self._open_prompt(PROMPT_SEARCH, self.search_term)

        @bindings.add("c-\\", filter=is_edit)
        def _replace_key(event: KeyPressEvent) -> None:
            self._open_prompt(PROMPT_REPLACE_FROM, self.replace_from)

        @bindings.add("c-_", filter=is_edit)
        def _goto_key(event: KeyPressEvent) -> None:
            self._open_prompt(PROMPT_GOTO)

        # ---- 剪切 / 粘贴 / 位置 ----
        @bindings.add("c-k", filter=is_edit)
        def _cut(event: KeyPressEvent) -> None:
            self._cut_current_line()

        @bindings.add("c-u", filter=is_edit)
        def _paste_key(event: KeyPressEvent) -> None:
            self._paste()

        @bindings.add("c-c", filter=is_edit)
        def _position(event: KeyPressEvent) -> None:
            self._show_position()

        # ---- 翻页（nano 用 ^Y / ^V，同时保留 PageUp / PageDown）----
        @bindings.add("c-y", filter=is_edit)
        def _page_up(event: KeyPressEvent) -> None:
            scroll_page_up(event)

        @bindings.add("c-v", filter=is_edit)
        def _page_down(event: KeyPressEvent) -> None:
            scroll_page_down(event)

        # 无 completer 时 tab 默认什么都不做，必须显式绑定
        @bindings.add("tab", filter=is_edit)
        def _tab(event: KeyPressEvent) -> None:
            if self.options.tabs_to_spaces:
                event.current_buffer.insert_text(" " * self.options.tab_size)
            else:
                event.current_buffer.insert_text("\t")

        # ---- 提示行 ----
        @bindings.add("enter", filter=is_prompt)
        def _prompt_submit(event: KeyPressEvent) -> None:
            self._submit_prompt()

        @bindings.add("c-c", filter=is_prompt)
        @bindings.add("escape", filter=is_prompt)
        def _prompt_cancel(event: KeyPressEvent) -> None:
            self._cancel_prompt()

        # ---- 确认（退出前是否保存）----
        @bindings.add("y", filter=is_confirm)
        @bindings.add("Y", filter=is_confirm)
        def _confirm_yes(event: KeyPressEvent) -> None:
            self._confirm_save()

        @bindings.add("n", filter=is_confirm)
        @bindings.add("N", filter=is_confirm)
        def _confirm_no(event: KeyPressEvent) -> None:
            self._confirm_discard()

        @bindings.add("c-c", filter=is_confirm)
        @bindings.add("escape", filter=is_confirm)
        def _confirm_abort(event: KeyPressEvent) -> None:
            self._confirm_cancel()

        # 兜底：确认模式下焦点仍在正文，未绑定的字母会被默认绑定插进正文
        @bindings.add(Keys.Any, filter=is_confirm, eager=True)
        def _confirm_ignore(event: KeyPressEvent) -> None:
            pass

        return bindings

    def run(self) -> None:
        self._app.run()


def _newline_label(newline: str) -> str:
    """把换行符转成可读名称，用于状态行展示。"""
    return {"\r\n": "CRLF", "\n": "LF", "\r": "CR"}.get(newline, "LF")


def main() -> None:
    # -h/--help 必须无副作用（不得读写文件、不得进入 TUI），放最开头直接退出
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", nargs="?", default="",
                        help="要编辑的文件（不存在则新建）")
    parser.add_argument("--encoding", default=None,
                        help="强制以指定编码读取（默认自动探测并在保存时沿用）")
    parser.add_argument("-l", "--linenumbers", action="store_true", help="显示行号")
    parser.add_argument("--tabsize", type=int, default=4, help="Tab 宽度（默认 4）")
    parser.add_argument("--tabstospaces", action="store_true",
                        help="Tab 键插入空格而非制表符")
    parser.add_argument("--no-color", action="store_true", help="关闭语法高亮")
    args = parser.parse_args()

    options = EditorOptions(
        encoding=args.encoding,
        line_numbers=args.linenumbers,
        tab_size=max(1, args.tabsize),
        tabs_to_spaces=args.tabstospaces,
        color=not args.no_color,
    )
    DuckEditApp(args.file, options).run()


if __name__ == "__main__":
    main()
