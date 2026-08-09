# -*- coding: utf-8 -*-
"""
duck-edit —— 基于 Textual 的双栏文本编辑器（左侧目录树 + 右侧编辑区）。

布局：
- 左侧：目录树（DirectoryTree，参考 duck-shell 的实现隐藏根节点、目录名后附子项数量）
- 右侧：文本编辑区（TextArea），语法高亮复用 duck_utils.syntax_util 的分词器

特性：
- 点击左侧文件即在右侧打开；保存时保留原编码（utf-8 / utf-8-sig / utf-16 / gbk 等）
  与原换行符（CRLF / LF / CR）
- 语法高亮由 duck_utils 的 SyntaxTokenizer 完成（按扩展名 detect_lang 推断语言）
- nano 风格快捷键：Ctrl+S 保存 / Ctrl+O 聚焦文件树 / Ctrl+G 跳转行 / Ctrl+Q 退出
- 撤销重做：Ctrl+Z 撤销 / Ctrl+Y 或 Ctrl+Shift+Z 重做（基于 TextArea 内置历史）
- 刷新：Ctrl+R 重新加载目录树；若当前文件被外部修改，无未保存改动时自动重新载入
- 编辑器下方命令框支持搜索（Ctrl+F 聚焦）：
    f <片段>     在当前目录（含子目录）按文件名搜索，回车打开匹配文件
    g <内容>     在当前打开的文件中搜索内容，回车跳转到对应行
    d <内容>     在当前目录（含子目录）的所有文本文件中搜索内容

用法：
  duck-edit [文件] [--path 起始目录] [-h]

说明：
  -h/--help 必须无副作用（不读写文件、不进入 TUI），放 main 最开头直接退出。
"""
import argparse
import codecs
import os
import sys
from dataclasses import dataclass
from typing import Callable, Optional

from rich.style import Style
from rich.text import Text

from textual.app import App, ComposeResult
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Footer, Header, Input, OptionList, Static, TextArea
from textual.widgets._tree import TreeNode

from duck_utils.syntax_util import SyntaxTokenizer, detect_lang
from duck_utils.os_util import is_windows


def _set_terminal_title(title: str) -> None:
    """设置终端标签页 / 窗口标题（跨平台，失败静默忽略）。

    现代终端（Windows Terminal、iTerm2、gnome-terminal 等）支持 OSC 转义序列
    （\\x1b]0;TITLE\\x07 同时设置图标名与窗口/标签页标题）；经典 Windows 控制台
    (conhost) 用 SetConsoleTitleW。退出后标题会保留为所设值。
    """
    try:
        if is_windows():
            try:
                import ctypes
                ctypes.windll.kernel32.SetConsoleTitleW(title)  # type: ignore
            except Exception:
                pass
        # OSC 0: 设置图标名 + 窗口/标签页标题
        sys.stdout.write("\x1b]0;%s\x07" % title)
        sys.stdout.flush()
    except Exception:
        pass

# 视为文本文件、点击左侧文件时允许打开的扩展名白名单（参考 duck-shell）
_TEXT_EXTS = frozenset({
    ".txt", ".py", ".pyw", ".sh", ".bat", ".cmd", ".ps1", ".md", ".rst",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".config",
    ".csv", ".tsv", ".log", ".xml", ".html", ".htm", ".css", ".js", ".mjs",
    ".ts", ".jsx", ".tsx", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp",
    ".java", ".go", ".rs", ".rb", ".php", ".sql", ".pl", ".lua", ".r",
    ".scala", ".kt", ".swift", ".gradle", ".mk", ".cmake",
    ".gitignore", ".gitattributes", ".dockerfile", ".editorconfig",
    ".properties", ".env", ".diff", ".patch", ".po", ".tex", ".adoc",
})

# duck_utils 的 token 类型 -> TextArea 主题（css 主题）的高亮名。
# 主题未定义的名称会被忽略（不高亮），因此这里只挑有把握映射的几类。
_KIND_TO_HL = {
    "comment": "comment",
    "string": "string",
    "number": "number",
    "keyword": "keyword",
    "symbol": "operator",
}


# ------------------------------------------------------------------ #
# 文件编解码：保留原编码与原换行符
# ------------------------------------------------------------------ #
def _detect_decode(data: bytes) -> "tuple[str, str]":
    """把文件字节解码为文本，返回 (文本, 实际 codec 名)。

    尝试顺序：BOM -> utf-8 -> gbk -> latin-1（兜底）。
    """
    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig"), "utf-8-sig"
    if data.startswith(codecs.BOM_UTF16_LE):
        return data.decode("utf-16"), "utf-16"
    if data.startswith(codecs.BOM_UTF16_BE):
        return data.decode("utf-16"), "utf-16"
    if data.startswith(codecs.BOM_UTF32_LE):
        return data.decode("utf-32"), "utf-32"
    if data.startswith(codecs.BOM_UTF32_BE):
        return data.decode("utf-32"), "utf-32"
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace"), "latin-1"


def _detect_newline(text: str) -> str:
    """按出现次数判断文本的主要换行符；没有换行符时返回 \\n。"""
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    if crlf > 0 and crlf >= lf and crlf >= cr:
        return "\r\n"
    if lf > 0 and lf >= cr:
        return "\n"
    if cr > 0:
        return "\r"
    return "\n"


def _read_file(path: str) -> "tuple[str, str, str]":
    """读取文件为编辑器文本（\\n 换行），返回 (文本, 编码, 原换行符)。"""
    with open(path, "rb") as fp:
        data = fp.read()
    decoded, encoding = _detect_decode(data)
    newline = _detect_newline(decoded)
    text = decoded.replace("\r\n", "\n").replace("\r", "\n")
    return text, encoding, newline


def _write_file(path: str, text: str, encoding: str, newline: str) -> int:
    """按原换行符 + 原编码写回文件，返回写入字节数。"""
    data = text.replace("\n", newline).encode(encoding)
    with open(path, "wb") as fp:
        fp.write(data)
    return len(data)


# ------------------------------------------------------------------ #
# 左侧目录树（参考 duck-shell 的 DuckDirTree）
# ------------------------------------------------------------------ #
class DuckDirTree(DirectoryTree):
    """目录树：隐藏根节点自身，直接展示当前工作目录内容。

    目录节点在名称后附加「直接子项数量」（文件与文件夹，灰色），与文件名区分；
    仅统计直接子项，不递归遍历，开销很低。
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.show_root = False

    def render_label(self, node: TreeNode, base_style: Style, style: Style) -> Text:
        label = super().render_label(node, base_style, style)
        if node._allow_expand and node.data is not None:
            try:
                count = sum(1 for _ in os.scandir(node.data.path))
            except OSError:
                count = 0
            label.append_text(Text("  (%d)" % count, style="#808080"))
        return label


def _is_text_file(path: str) -> bool:
    """判断文件是否应作为文本打开（扩展名白名单 + 二进制嗅探）。"""
    ext = os.path.splitext(path)[1].lower()
    if ext in _TEXT_EXTS:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
    except (OSError, IOError):
        return False
    if not chunk:
        return True
    if b"\x00" in chunk:
        return False
    texty = 0
    for b in chunk:
        if b in (9, 10, 13) or 32 <= b <= 126 or 128 <= b <= 255:
            texty += 1
    return texty / len(chunk) > 0.7


# ------------------------------------------------------------------ #
# 右侧编辑区：用 duck_utils 的 SyntaxTokenizer 做高亮
# ------------------------------------------------------------------ #
class DuckTextArea(TextArea):
    """TextArea 子类：语法高亮改用 duck_utils.syntax_util 的分词器。

    TextArea 默认高亮基于 tree-sitter，且把高亮结果存进
    ``self._highlights[行] = [(起点列, 终点列, 主题高亮名), ...]``，渲染时按
    主题 ``syntax_styles`` 取样式。这里覆写 ``_build_highlight_map``，改用
    ``SyntaxTokenizer`` 逐行（保持跨行三引号 / 块注释状态）分词，把 token 类型
    映射到主题高亮名，从而复用 duck_utils 的高亮逻辑。
    """

    def __init__(self, *args, duck_lang: str = "default", **kwargs) -> None:
        # 必须在 super().__init__() 之前赋值：初始化期间基类可能触发
        # _build_highlight_map（reactive watch），那时就要用到它
        self._duck_lang = duck_lang
        super().__init__(*args, **kwargs)

    def set_duck_language(self, lang: str) -> None:
        """切换高亮语言（按文件名 detect_lang 得到），并刷新高亮。"""
        self._duck_lang = lang
        self._build_highlight_map()

    def _build_highlight_map(self) -> None:
        highlights = getattr(self, "_highlights", None)
        # 初始化早期（基类还没建好 document / highlights）时直接返回，避免异常
        if highlights is None or not hasattr(self, "document"):
            return
        self._line_cache.clear()
        highlights.clear()
        tokenizer = SyntaxTokenizer(self._duck_lang)
        line_count = self.document.line_count
        for row in range(line_count):
            line_text = self.document.get_line(row)
            col = 0
            for tok in tokenizer.tokenize(line_text):
                name = _KIND_TO_HL.get(tok.kind)
                if name is None:
                    col += len(tok.text)
                    continue
                start = col
                end = col + len(tok.text)
                highlights[row].append((start, end, name))
                col = end


# ------------------------------------------------------------------ #
# 通用输入弹窗（跳转行 / 另存为 复用）
# ------------------------------------------------------------------ #
class PromptScreen(ModalScreen[str]):
    """居中对话框：标题 + 单行输入框，回车返回输入内容，Esc 返回 None。"""

    CSS = """
    PromptScreen { align: center middle; }
    #dialog {
        width: 60%;
        max-width: 60;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #label { color: $text-muted; padding-bottom: 1; }
    """

    def __init__(self, prompt: str, default: str = "") -> None:
        super().__init__()
        self._prompt = prompt
        self._default = default

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(self._prompt, id="label")
            yield Input(self._default, id="input")

    def on_mount(self) -> None:
        self.query_one("#input", Input).focus()

    @on(Input.Submitted)
    def on_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_key(self, event) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)


# ------------------------------------------------------------------ #
# 退出确认弹窗
# ------------------------------------------------------------------ #
class ConfirmQuit(ModalScreen[str]):
    """退出确认：保存并退出 / 不保存退出 / 取消。"""

    CSS = """
    ConfirmQuit { align: center middle; }
    #dialog {
        width: 50%;
        max-width: 50;
        border: round $warning;
        background: $surface;
        padding: 1 2;
    }
    #title { padding-bottom: 1; color: $warning; }
    #row { height: auto; }
    #row > Button { width: 1fr; min-width: 0; margin: 0 1 0 0; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("缓冲区已修改，是否保存？", id="title")
            with Horizontal(id="row"):
                yield Button("保存并退出", id="save", variant="primary")
                yield Button("不保存退出", id="discard", variant="warning")
                yield Button("取消", id="cancel")

    def action_cancel(self) -> None:
        self.dismiss("cancel")

    def on_key(self, event) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss("cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "save":
            self.dismiss("save")
        elif bid == "discard":
            self.dismiss("discard")
        elif bid == "cancel":
            self.dismiss("cancel")


# ------------------------------------------------------------------ #
# 搜索结果弹窗
# ------------------------------------------------------------------ #
@dataclass
class SearchResult:
    """单条搜索结果：展示文本 + 命中文件 + 命中行（1-based，可为 None）。"""
    label: str
    path: str
    line: Optional[int]


class SearchResultScreen(ModalScreen[Optional[SearchResult]]):
    """居中结果列表：方向键 / 鼠标选择，回车返回所选结果，Esc 返回 None。"""

    CSS = """
    SearchResultScreen { align: center middle; }
    #box {
        width: 80%;
        height: 80%;
        border: round $accent;
        background: $surface;
        padding: 1 1;
    }
    #title { color: $text-muted; padding: 0 0 1 0; }
    #list { height: 1fr; }
    """

    def __init__(self, title: str, results: "list[SearchResult]") -> None:
        super().__init__()
        self._title = title
        self._results = results

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(self._title, id="title")
            yield OptionList(id="list")

    def on_mount(self) -> None:
        opt = self.query_one("#list", OptionList)
        if not self._results:
            opt.add_option("（无匹配结果）")
        else:
            for r in self._results:
                opt.add_option(r.label)
        opt.focus()

    @on(OptionList.OptionSelected, "#list")
    def on_select(self, event: OptionList.OptionSelected) -> None:
        if not self._results:
            self.dismiss(None)
            return
        # 选项与结果一一对应（无结果时仅占位项，已在上面拦截）
        self.dismiss(self._results[event.option_index])

    def on_key(self, event) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)


# ------------------------------------------------------------------ #
# 主应用
# ------------------------------------------------------------------ #
class DuckEditApp(App):
    TITLE = "duck-edit"
    SUB_TITLE = "双栏文本编辑器"

    CSS = """
    #sidebar {
        width: 30%;
        height: 1fr;
        border: round $accent;
        padding: 0 1;
    }
    #btnbar { height: auto; width: 100%; }
    #btnbar > Button {
        width: 1fr; min-width: 0; margin: 0 1 0 0;
    }
    #tree { height: 1fr; }
    #main { height: 1fr; }
    #status {
        height: auto;
        padding: 0 1;
        background: $accent;
        color: $text;
    }
    #editor { height: 1fr; border: round $accent; }
    #cmd {
        height: auto;
        margin-top: 1;
        border: round $accent;
    }
    #cmd:focus { border: round $warning; }
    """

    BINDINGS = [
        ("ctrl+s", "save", "保存"),
        ("ctrl+o", "focus_tree", "文件树"),
        ("ctrl+g", "goto", "跳转行"),
        ("ctrl+f", "focus_cmd", "命令框"),
        ("ctrl+z", "undo", "撤销"),
        ("ctrl+y", "redo", "重做"),
        ("ctrl+shift+z", "redo", "重做"),
        ("ctrl+r", "refresh", "刷新"),
        ("ctrl+q", "quit", "退出"),
    ]

    def __init__(self, start_dir: str, open_file: Optional[str] = None) -> None:
        super().__init__()
        self.start_dir: str = os.path.abspath(start_dir)
        self._initial_file: Optional[str] = open_file
        # 当前文件状态
        self.current_path: Optional[str] = None
        self._saved_text: str = ""
        self._encoding: str = "utf-8"
        self._newline: str = "\n"
        # 当前文件在磁盘上的 (mtime, size) 快照，用于刷新时检测外部改动
        self._disk_sig: Optional["tuple[float, int]"] = None

    # ------------------------------------------------------------------ #
    # 布局
    # ------------------------------------------------------------------ #
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                with Horizontal(id="btnbar"):
                    yield Button("↑上级", id="up", variant="default")
                    yield Button("刷新", id="refresh_btn", variant="default")
                    yield Button("保存", id="save_btn", variant="primary")
                    yield Button("退出", id="quit_btn", variant="default")
                yield DuckDirTree(self.start_dir, id="tree")
            with Vertical(id="main"):
                yield Static("[ 未打开文件 ]", id="status")
                yield DuckTextArea(id="editor", show_line_numbers=True)
                yield Input(
                    id="cmd",
                    placeholder="命令: f 文件名 | g 文件内容 | d 目录内容  (Ctrl+F 聚焦)",
                )
        yield Footer()

    def on_mount(self) -> None:
        if self._initial_file and os.path.isfile(self._initial_file):
            self.open_file(os.path.abspath(self._initial_file))
        else:
            self.query_one("#editor", DuckTextArea).focus()

    # ------------------------------------------------------------------ #
    # 辅助
    # ------------------------------------------------------------------ #
    def _editor(self) -> DuckTextArea:
        return self.query_one("#editor", DuckTextArea)

    def _tree(self) -> DuckDirTree:
        return self.query_one("#tree", DuckDirTree)

    def _is_dirty(self) -> bool:
        return self._editor().text != self._saved_text

    def _update_status(self) -> None:
        editor = self._editor()
        row, col = editor.selection.end
        total = editor.document.line_count
        name = self.current_path or "[ 未命名 ]"
        lang = editor._duck_lang
        flag = " [已修改]" if self._is_dirty() else ""
        self.query_one("#status", Static).update(
            "%s   %s   行 %d/%d 列 %d   %s%s"
            % (name, lang, row + 1, total, col + 1, self._encoding, flag)
        )

    # ------------------------------------------------------------------ #
    # 打开 / 保存
    # ------------------------------------------------------------------ #
    def open_file(self, path: str) -> None:
        if not _is_text_file(path):
            self.notify("已跳过二进制文件: %s" % path, severity="warning")
            return
        try:
            text, encoding, newline = _read_file(path)
        except OSError as e:
            self.notify("读取失败: %s" % e, severity="error")
            return
        editor = self._editor()
        editor._duck_lang = detect_lang(path)
        editor.load_text(text)
        self.current_path = path
        self._saved_text = text
        self._encoding = encoding
        self._newline = newline
        self._disk_sig = self._disk_stat(path)
        _set_terminal_title("duck-edit - %s" % os.path.basename(path))
        self._update_status()
        editor.focus()

    @staticmethod
    def _disk_stat(path: str) -> "Optional[tuple[float, int]]":
        """取文件 (mtime, size) 快照；读取失败时返回 None。"""
        try:
            st = os.stat(path)
        except OSError:
            return None
        return (st.st_mtime, st.st_size)

    def _do_save(self, path: str) -> None:
        try:
            size = _write_file(path, self._editor().text, self._encoding, self._newline)
        except (UnicodeEncodeError, OSError) as e:
            self.notify("保存失败: %s" % e, severity="error")
            return
        self.current_path = path
        self._saved_text = self._editor().text
        self._disk_sig = (os.path.getmtime(path), size)
        self.notify("已保存 %d 字节: %s" % (size, path))
        self._update_status()

    def action_save(self) -> None:
        if self.current_path:
            self._do_save(self.current_path)
        else:
            self.push_screen(
                PromptScreen("保存到:", default=os.path.basename(self.current_path or "")),
                self._on_save_as,
            )

    def _on_save_as(self, value: Optional[str]) -> None:
        if not value:
            return
        if os.path.isabs(value):
            path = value
        else:
            base = os.path.dirname(self.current_path) if self.current_path else self.start_dir
            path = os.path.join(base, value)
        self._do_save(path)

    def action_focus_tree(self) -> None:
        self._tree().focus()

    def action_goto(self) -> None:
        self.push_screen(PromptScreen("跳转到行:", ""), self._on_goto)

    def _on_goto(self, value: Optional[str]) -> None:
        if not value:
            return
        try:
            lineno = int(value.strip())
        except ValueError:
            self.notify("行号无效: %s" % value, severity="error")
            return
        if lineno < 1:
            lineno = 1
        self._editor().move_cursor((lineno - 1, 0), center=True)
        self._editor().focus()

    async def action_quit(self) -> None:
        if not self._is_dirty():
            self.exit()
            return
        self.push_screen(ConfirmQuit(), self._on_quit_choice)

    def _on_quit_choice(self, choice: Optional[str]) -> None:
        if choice == "discard":
            self.exit()
        elif choice == "save":
            if self.current_path:
                self._do_save(self.current_path)
                self.exit()
            else:
                self.push_screen(
                    PromptScreen("保存到:", default=""), self._on_save_as_then_quit
                )

    def _on_save_as_then_quit(self, value: Optional[str]) -> None:
        if not value:
            return
        if os.path.isabs(value):
            path = value
        else:
            path = os.path.join(self.start_dir, value)
        self._do_save(path)
        self.exit()

    def action_focus_cmd(self) -> None:
        self.query_one("#cmd", Input).focus()

    def action_undo(self) -> None:
        """撤销上一次编辑（TextArea 内置历史），并刷新状态行。"""
        editor = self._editor()
        editor.undo()
        self._update_status()

    def action_redo(self) -> None:
        """重做被撤销的编辑（TextArea 内置历史），并刷新状态行。"""
        editor = self._editor()
        editor.redo()
        self._update_status()

    def action_refresh(self) -> None:
        """刷新左侧目录树，并在文件被外部修改时按规则重载当前文件。

        - 重加载目录树（外部新增 / 删除 / 重命名的文件即时出现）
        - 若当前文件在磁盘上被改动：
          * 无未保存改动 -> 自动重新载入，提示「已从磁盘重新加载」
          * 有未保存改动 -> 仅警告，避免覆盖编辑器中的内容
        """
        self._tree().reload()
        if not self.current_path:
            return
        new_sig = self._disk_stat(self.current_path)
        if new_sig is None or new_sig == self._disk_sig:
            return
        if self._is_dirty():
            self.notify(
                "磁盘文件已被外部修改，保存将覆盖外部版本", severity="warning"
            )
            return
        self.open_file(self.current_path)
        self.notify("已从磁盘重新加载: %s" % self.current_path)

    # ------------------------------------------------------------------ #
    # 命令 / 搜索
    # ------------------------------------------------------------------ #
    @on(Input.Submitted, "#cmd")
    def on_cmd_submitted(self, event: Input.Submitted) -> None:
        self._run_command(event.value)

    def _run_command(self, raw: str) -> None:
        """解析并执行命令框命令。

        语法：
          f <片段> / find <片段>   当前目录（含子目录）按文件名搜索
          g <内容> / grep <内容>   当前打开文件内搜索内容
          d <内容> / grepdir <内容> 当前目录（含子目录）文本文件内搜索内容
        """
        raw = raw.strip()
        if not raw:
            return
        parts = raw.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        if cmd in ("f", "find"):
            self._search_filenames(arg)
        elif cmd in ("g", "grep"):
            self._search_current_file(arg)
        elif cmd in ("d", "grepdir"):
            self._search_dir_content(arg)
        else:
            self.notify(
                "未知命令: %s（支持 f/find, g/grep, d/grepdir）" % cmd,
                severity="warning",
            )

    def _search_filenames(self, pattern: str) -> None:
        if not pattern:
            self.notify("用法: f <文件名片段>", severity="warning")
            return
        root = self._tree().path
        pat = pattern.lower()
        results: "list[SearchResult]" = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                if pat in fn.lower():
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, root)
                    results.append(SearchResult(rel, full, None))
        self._show_results('文件名搜索: "%s"' % pattern, results)

    def _search_current_file(self, pattern: str) -> None:
        if not self.current_path:
            self.notify("当前未打开文件，无法搜索内容", severity="warning")
            return
        if not pattern:
            self.notify("用法: g <内容>", severity="warning")
            return
        pat = pattern.lower()
        text = self._editor().text
        results: "list[SearchResult]" = []
        for i, line in enumerate(text.split("\n"), 1):
            if pat in line.lower():
                results.append(
                    SearchResult("%d: %s" % (i, line.rstrip()), self.current_path, i)
                )
        self._show_results('当前文件内容搜索: "%s"' % pattern, results)

    def _search_dir_content(self, pattern: str) -> None:
        if not pattern:
            self.notify("用法: d <内容>", severity="warning")
            return
        root = self._tree().path
        pat = pattern.lower()
        # 跳过大概率无意义且耗时的目录
        _SKIP_DIRS = frozenset({".git", "node_modules", "__pycache__", ".venv", "venv"})
        results: "list[SearchResult]" = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                if not _is_text_file(full):
                    continue
                try:
                    text, _enc, _nl = _read_file(full)
                except (OSError, UnicodeDecodeError):
                    continue
                rel = os.path.relpath(full, root)
                for i, line in enumerate(text.split("\n"), 1):
                    if pat in line.lower():
                        results.append(
                            SearchResult("%s:%d: %s" % (rel, i, line.rstrip()), full, i)
                        )
        self._show_results('目录内容搜索: "%s"' % pattern, results)

    def _show_results(self, title: str, results: "list[SearchResult]") -> None:
        if not results:
            self.notify("未找到匹配", severity="warning")
            return
        self.push_screen(
            SearchResultScreen(title, results), self._on_search_result
        )

    def _on_search_result(self, result: Optional[SearchResult]) -> None:
        if result is None:
            return
        self.open_file(result.path)
        if result.line is not None and self.current_path == result.path:
            self._editor().move_cursor((result.line - 1, 0), center=True)

    # ------------------------------------------------------------------ #
    # 事件
    # ------------------------------------------------------------------ #
    def on_key(self, event) -> None:
        # 光标移动 / 编辑后刷新状态行（行号、列号、已修改标记）
        if self.focused is self._editor():
            self._update_status()

    @on(DirectoryTree.FileSelected)
    def on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.open_file(str(event.path))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "up":
            parent = os.path.dirname(self._tree().path)
            if parent and parent != self._tree().path:
                self._tree().path = parent
        elif bid == "refresh_btn":
            self.action_refresh()
        elif bid == "save_btn":
            self.action_save()
        elif bid == "quit_btn":
            await self.action_quit()


def main() -> None:
    # -h/--help 必须无副作用，放最开头直接退出
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="基于 Textual 的双栏文本编辑器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", nargs="?", default="", help="启动时打开的文件")
    parser.add_argument("--path", default=".", help="目录树初始目录（默认当前目录）")
    args = parser.parse_args()

    start_dir = args.path if os.path.isdir(args.path) else os.getcwd()
    initial = args.file if args.file else None
    # 启动即修改终端标签页标题（无文件时显示起始目录名）
    if initial:
        _set_terminal_title("duck-edit - %s" % os.path.basename(os.path.abspath(initial)))
    else:
        _set_terminal_title("duck-edit - %s" % os.path.basename(os.path.abspath(start_dir)))
    DuckEditApp(start_dir=start_dir, open_file=initial).run()


if __name__ == "__main__":
    main()
