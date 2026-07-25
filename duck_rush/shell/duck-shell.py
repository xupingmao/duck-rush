# -*- coding: utf-8 -*-
"""
duck-shell —— 基于 Textual 的双栏终端工具。

布局：
- 左侧：目录树（DirectoryTree），点击目录即可把右侧终端的工作目录切到该目录
- 右侧：命令行终端（RichLog + Input），基于 subprocess 执行命令并流式输出

与普通终端的一致性：
- 维持当前工作目录（cwd），`cd` / 相对路径 / 绝对路径均可
- 内建命令：cd / pwd / clear / exit（其余命令交给系统 shell 执行）
- 命令输出实时流式显示

上下文限制（防内存膨胀）：
- 右侧终端使用 RichLog(max_lines=...) 自动裁剪历史行
- 默认最多保留 5000 行，可用 --max-lines 调整；长输出 / 长时间运行的命令不会无限占用内存
"""
import os
import sys
import asyncio
import argparse
import subprocess
from dataclasses import dataclass
from typing import Optional

from rich.text import Text

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.suggester import Suggester
from textual import on
from duck_utils.jsonl_util import JsonlStore
from textual.widgets import (
    DirectoryTree,
    RichLog,
    Input,
    Static,
    Header,
    Footer,
    Button,
    Label,
)


DEFAULT_MAX_LINES = 5000

# ------------------------------------------------------------------ #
# 收藏夹 DAO 层：data class（实体）+ dao class（持久化）
# ------------------------------------------------------------------ #
@dataclass
class Bookmark:
    """收藏夹中的一条收藏：一个目录路径。"""

    path: str


class BookmarkDao:
    """收藏夹数据访问层，使用 JSONL（每行一个 JSON 对象）持久化。

    存储位置：<项目根>/data/duck-shell/bookmark/bookmarks.jsonl
    （data/ 已被 gitignore；duck-shell 相关持久化统一放在 data/duck-shell 下）。
    底层 JSONL 读写委托给 duck_utils.JsonlStore。
    """

    def __init__(self, root: Optional[str] = None) -> None:
        if root is None:
            # duck_rush/shell/duck-shell.py -> 项目根 = 上溯两级
            here = os.path.dirname(os.path.abspath(__file__))
            root = os.path.join(
                os.path.dirname(os.path.dirname(here)),
                "data", "duck-shell", "bookmark",
            )
        self.dir: str = root
        self.store: "JsonlStore" = JsonlStore(os.path.join(root, "bookmarks.jsonl"))

    # ---- 内部读写（委托 JsonlStore，仅做字段映射）----
    def _read_all(self) -> list:
        return [Bookmark(path=rec["path"])
                for rec in self.store.read_all()
                if rec.get("path")]

    def _write_all(self, items: list) -> None:
        self.store.write_all([{"path": bm.path} for bm in items])

    @staticmethod
    def _norm(path: str) -> str:
        return os.path.normcase(os.path.abspath(path))

    # ---- 对外接口 ----
    def all(self) -> list:
        """返回全部收藏（Bookmark 列表）。"""
        return self._read_all()

    def has(self, path: str) -> bool:
        """指定目录是否已被收藏（按规范化绝对路径比较）。"""
        norm = self._norm(path)
        return any(self._norm(b.path) == norm for b in self._read_all())

    def add(self, path: str) -> None:
        if self.has(path):
            return
        items = self._read_all()
        items.append(Bookmark(path=path))
        self._write_all(items)

    def remove(self, path: str) -> None:
        norm = self._norm(path)
        items = [b for b in self._read_all() if self._norm(b.path) != norm]
        self._write_all(items)

    def toggle(self, path: str) -> bool:
        """切换收藏状态，返回切换后的「是否已收藏」。"""
        if self.has(path):
            self.remove(path)
            return False
        self.add(path)
        return True


class DuckDirTree(DirectoryTree):
    """目录树：隐藏根节点自身，直接展示当前工作目录内容。"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.show_root = False

# subprocess 输出按行流式读取时的块大小
_READ_CHUNK = 4096

# 命令前加 ! 可强制以「附加（attach）模式」运行（交接屏幕控制权给真实终端）。
# 总是需要交接的命令（编辑器 / 分页器 / shell / 全屏 TUI），无论带什么参数。
ALWAYS_ATTACH = {
    "vim", "vi", "nvim", "nano", "emacs", "ed", "less", "more", "most", "man",
    "bash", "sh", "zsh", "fish", "cmd", "powershell", "pwsh",
    "top", "htop", "ranger", "lf", "mutt", "irssi", "tmux", "screen", "btm", "btop",
}
# 解释器类：仅当「裸命令」（无参数，进入 REPL）时才交接；
# 带 -c / 脚本参数时为非交互，仍走普通捕获输出。
REPL_ATTACH = {
    "python", "python3", "py", "ipython", "node", "ruby", "perl", "php",
    "lua", "sqlite3", "mysql", "psql", "ghci",
}


def decode_bytes(data: bytes) -> str:
    """鲁棒解码：依次尝试 utf-8 / gbk（中文 Windows 常见）/ latin-1。"""
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


# 内置命令（可被 Tab 补全的首个 token）
BUILTIN_COMMANDS = ["cd", "pwd", "clear", "cls", "exit", "quit"]


class ShellInput(Input):
    """命令行输入框：把 Tab 键绑定为「接受补全建议」（Textual 默认 Tab 用于切换焦点）。"""

    BINDINGS = [
        Binding("tab", "cursor_right", "补全", show=False),
    ]

    def __init__(self, *args, history: Optional[list] = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # 与所属 App 共享同一 list 引用，App 侧原地修改即可同步
        self.history: list = history if history is not None else []


class CommandSuggester(Suggester):
    """根据已输入的首个 token（命令名）给出补全建议；Tab 即可接受。

    候选来源：内置命令 + 历史命令的首个 token，方便召回常用命令。
    """

    def __init__(self, commands: list, history_provider) -> None:
        # 历史会变化，关闭缓存以保证建议实时
        super().__init__(case_sensitive=False, use_cache=False)
        self._commands = sorted(set(commands))
        self._history_provider = history_provider

    async def get_suggestion(self, value: str) -> "str | None":
        # value 已被 casefold（case_sensitive=False）
        if not value or value.endswith(" ") or " " in value:
            return None
        candidates = list(self._commands)
        for hist in self._history_provider():
            token = hist.strip().split(" ", 1)[0]
            if token:
                candidates.append(token)
        # 去重（大小写不敏感），保持顺序
        seen = set()
        unique = []
        for c in candidates:
            cf = c.casefold()
            if cf not in seen:
                seen.add(cf)
                unique.append(c)
        matches = [c for c in unique if c.casefold().startswith(value)]
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        # 多个候选：补全到最长公共前缀；若已无进展则给出第一个
        prefix = os.path.commonprefix(matches)
        if prefix and prefix != value:
            return prefix
        return matches[0]


class DuckShellApp(App):
    TITLE = "duck-shell"
    SUB_TITLE = "双栏终端"

    CSS = """
    #sidebar {
        width: 32%;
        height: 1fr;
        border: round $accent;
        padding: 0 1;
    }
    #btnbar {
        height: auto;
        width: 100%;
    }
    #btnbar > Button {
        width: 1fr;
        min-width: 0;
        margin: 0 1 0 0;
    }
    #tree {
        height: 1fr;
    }
    #rightcol {
        height: 1fr;
    }
    #terminal {
        height: 1fr;
        border: round $accent;
    }
    #input_area {
        height: auto;
    }
    #prompt {
        height: auto;
        padding: 0 1;
        color: $text-muted;
    }
    #cmdline {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("ctrl+l", "clear_screen", "清屏"),
        ("ctrl+q", "quit", "退出"),
        ("pageup", "scroll_terminal(-1)", "终端上滚"),
        ("pagedown", "scroll_terminal(1)", "终端下滚"),
    ]

    def __init__(self, start_path: str = ".", max_lines: int = DEFAULT_MAX_LINES):
        super().__init__()
        self.cwd: str = os.path.abspath(start_path)
        # 子进程环境（继承当前环境变量，命令执行时可继续累积修改）
        self.env: dict = dict(os.environ)
        self.max_lines: int = max_lines
        self.busy: bool = False
        # 收藏夹数据访问层
        self.dao: BookmarkDao = BookmarkDao()
        # 命令历史（上下方向键切换）；与输入框共享同一 list 引用
        self.history: list = []
        self._hist_idx: Optional[int] = None
        self._draft: str = ""
        # 命令历史持久化到 data/duck-shell/history.jsonl（与收藏夹同处 duck-shell 目录）
        self._history_store: JsonlStore = JsonlStore(
            os.path.join(os.path.dirname(self.dao.dir), "history.jsonl")
        )

    # ------------------------------------------------------------------ #
    # 布局
    # ------------------------------------------------------------------ #
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                # 按钮组（同一行）：返回上级目录 / 收藏(或取消收藏) / 收藏夹
                # 文字过长时缩写，鼠标悬浮通过 tooltip 展示完整文字
                with Horizontal(id="btnbar"):
                    yield Button("[↑上级]", id="up_entry", variant="default")
                    yield Button("[收藏]", id="fav_toggle", variant="default")
                    yield Button("[收藏夹]", id="fav_open", variant="default")
                yield DuckDirTree(self.cwd, id="tree")
            with Vertical(id="rightcol"):
                yield RichLog(id="terminal",
                              max_lines=self.max_lines,
                              wrap=True,
                              highlight=False,
                              markup=False)
                with Vertical(id="input_area"):
                    yield Static(self._prompt_text(), id="prompt")
                    yield ShellInput(
                        id="cmdline",
                        placeholder="输入命令，回车执行（Tab 补全 / ↑↓ 历史）",
                        history=self.history,
                        suggester=CommandSuggester(
                            BUILTIN_COMMANDS, lambda: self.history
                        ),
                    )
        yield Footer()

    # ------------------------------------------------------------------ #
    # 辅助
    # ------------------------------------------------------------------ #
    def _prompt_text(self) -> str:
        return self.cwd + "> "

    def _term(self) -> RichLog:
        return self.query_one("#terminal", RichLog)

    def _write(self, text: str) -> None:
        # RichLog 每调用一次 write 即为独立一行，故去掉调用方可能附带的多余换行，
        # 避免行间出现多余空行（行间距）。
        # 用 Text.from_ansi 解析命令输出的 ANSI 转义颜色（同时不影响本应用的普通文本）。
        if text.endswith("\n"):
            text = text[:-1]
        self._term().write(Text.from_ansi(text))

    def on_mount(self) -> None:
        self._write("duck-shell 已启动。")
        self._write("左侧点击目录可切换右侧工作目录；按钮组可「返回上级目录 / 收藏当前目录 / 打开收藏夹」；")
        self._write("输入 exit 退出；Ctrl+L 清屏；PageUp/PageDown 滚动面板；交互式命令（python/vim/top…）自动交接屏幕控制权。")
        # 按钮组悬浮提示（缩写按钮展示完整含义）
        self.query_one("#up_entry", Button).tooltip = "返回上级目录"
        self.query_one("#fav_toggle", Button).tooltip = "收藏 / 取消收藏 当前目录"
        self.query_one("#fav_open", Button).tooltip = "打开收藏夹"
        self._load_history()
        self._refresh_fav_button()
        self.query_one("#cmdline", Input).focus()

    # ------------------------------------------------------------------ #
    # 命令历史（上下方向键切换，持久化到 data/duck-shell/history.jsonl）
    # ------------------------------------------------------------------ #
    def _load_history(self) -> None:
        """从磁盘加载历史到 self.history（原地修改，保持输入框持有的同一引用）。"""
        self.history.clear()
        for rec in self._history_store.read_all():
            cmd = rec.get("cmd")
            if cmd:
                self.history.append(cmd)
        # 仅保留最近若干条，避免无限增长
        if len(self.history) > 500:
            del self.history[: len(self.history) - 500]
        self._hist_idx = None

    def _save_history(self, cmd: str) -> None:
        """追加一条历史并落盘（忽略与上一条重复的内容）。"""
        if self.history and self.history[-1] == cmd:
            return
        self.history.append(cmd)
        if len(self.history) > 500:
            del self.history[: len(self.history) - 500]
        self._history_store.write_all(
            [{"cmd": c} for c in self.history], max_records=500, atomic=True
        )
        self._hist_idx = None

    def on_key(self, event) -> None:
        # 仅在命令行输入框聚焦时处理上下方向键的历史切换
        if self.focused is not self.query_one("#cmdline", ShellInput):
            return
        inp = self.query_one("#cmdline", ShellInput)
        if event.key == "up":
            if not self.history:
                return
            event.stop()
            if self._hist_idx is None:
                self._draft = inp.value
                self._hist_idx = len(self.history) - 1
            else:
                self._hist_idx = max(0, self._hist_idx - 1)
            inp.value = self.history[self._hist_idx]
            inp.cursor_position = len(inp.value)
        elif event.key == "down":
            if self._hist_idx is None:
                return
            event.stop()
            self._hist_idx += 1
            if self._hist_idx >= len(self.history):
                self._hist_idx = None
                inp.value = self._draft
            else:
                inp.value = self.history[self._hist_idx]
            inp.cursor_position = len(inp.value)

    def _refresh_fav_button(self) -> None:
        """根据当前目录是否已被收藏，刷新 [收藏]/[取消收藏] 按钮文案。"""
        btn = self.query_one("#fav_toggle", Button)
        btn.label = "取消收藏" if self.dao.has(self.cwd) else "收藏"

    # ------------------------------------------------------------------ #
    # 目录树联动
    # ------------------------------------------------------------------ #
    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        if event.path is None:
            return
        self._change_dir(str(event.path))

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self._write("[文件] %s\n" % str(event.path))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "up_entry":
            self._change_dir("..")
        elif bid == "fav_toggle":
            self.dao.toggle(self.cwd)
            self._refresh_fav_button()
        elif bid == "fav_open":
            self.push_screen(BookmarkScreen(self.dao), self._on_bookmark_picked)

    def _on_bookmark_picked(self, path) -> None:
        """收藏夹弹窗选中某项后回调：跳转到该目录。"""
        if path:
            self._change_dir(path)

    def _change_dir(self, target: str) -> None:
        if not target:
            new = os.path.expanduser("~")
        elif os.path.isabs(target):
            new = target
        else:
            new = os.path.abspath(os.path.join(self.cwd, target))
        if not os.path.isdir(new):
            self._write("cd: 不是有效目录: %s\n" % new)
            return
        self.cwd = new
        self.query_one("#prompt", Static).update(self._prompt_text())
        # 重新设定目录树根节点，使左侧始终展示当前工作目录内容
        self.query_one("#tree", DirectoryTree).path = new
        # 切换目录后，当前目录的收藏状态可能变化
        self._refresh_fav_button()

    # ------------------------------------------------------------------ #
    # 命令输入与执行
    # ------------------------------------------------------------------ #
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.busy:
            return
        cmd = event.value.strip()
        self.query_one("#cmdline", Input).value = ""
        if cmd:
            self._save_history(cmd)
        await self._handle(cmd)

    @staticmethod
    def _is_attach(cmd: str) -> bool:
        """判断命令是否应以「附加模式」运行（交接屏幕控制权给真实终端）。"""
        s = cmd.strip()
        if not s:
            return False
        if s.startswith("!"):
            return True
        tokens = s.split()
        first = os.path.basename(tokens[0])
        if first.lower().endswith(".exe"):
            first = first[:-4]
        low = first.lower()
        if low in ALWAYS_ATTACH:
            return True
        if low in REPL_ATTACH:
            # 仅裸命令（无参数，进入 REPL）才交接；python -c / python xxx.py 仍走普通捕获
            return len(tokens) == 1
        return False

    async def _handle(self, cmd: str) -> None:
        if not cmd:
            return
        # 回显命令（shell 风格）
        self._write("%s %s\n" % (self._prompt_text(), cmd))

        low = cmd.lower()
        if low in ("exit", "quit"):
            self.exit()
            return
        if low in ("clear", "cls"):
            self._term().clear()
            return
        if low == "pwd":
            self._write(self.cwd + "\n")
            return
        if cmd == "cd" or cmd.startswith("cd ") or cmd.startswith("cd\t"):
            self._change_dir(cmd[2:].strip())
            return

        if self._is_attach(cmd):
            await self._run_attached(cmd)
            return

        await self._run_shell(cmd)

    async def _run_attached(self, cmd: str) -> None:
        """附加模式：把真实终端的控制权整个交给交互式命令，退出后自动恢复界面。

        若当前环境不支持交接（如无真实终端），则退化为普通捕获输出。
        """
        self.busy = True
        try:
            run = cmd.strip()[1:].strip() if cmd.strip().startswith("!") else cmd
            handed_off = False
            try:
                with self.suspend():
                    # 此处阻塞在真实终端上，交由子进程完全控制屏幕
                    subprocess.run(run, shell=True, cwd=self.cwd, env=self.env)
                handed_off = True
                label = run.split()[0] if run.split() else run
                self._write("<<< 已返回 duck-shell（刚才运行：%s）\n" % label)
            except Exception:
                # 交接失败（如无真实终端），退化为普通捕获
                pass
            if not handed_off:
                await self._run_shell(run)
        except Exception as e:  # noqa
            self._write("执行失败: %s\n" % e)
        finally:
            self.busy = False
            self.query_one("#cmdline", Input).focus()

    async def _run_shell(self, cmd: str) -> None:
        self.busy = True
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=self.cwd,
                env=self.env,
                # 关键：子进程必须完全脱离本应用的终端，否则会继承 stdin 与
                # Textual 抢夺终端输入，导致整个界面（两侧滚动条）卡死、命令也像卡住。
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            assert proc.stdout is not None
            buffer = b""
            while True:
                raw = await proc.stdout.read(_READ_CHUNK)
                if not raw:
                    if buffer:
                        self._write(decode_bytes(buffer))
                    break
                buffer += raw
                # 仅解码完整行，保留末尾可能不完整的分片，避免多字节字符被截断
                parts = buffer.split(b"\n")
                buffer = parts.pop()
                for line in parts:
                    self._write(decode_bytes(line) + "\n")
            await proc.wait()
            if proc.returncode not in (0, None):
                self._write("[退出码 %s]" % proc.returncode)
        except Exception as e:  # 任意异常都不应让界面崩溃
            self._write("执行失败: %s\n" % e)
        finally:
            self.busy = False
            self.query_one("#cmdline", Input).focus()

    # ------------------------------------------------------------------ #
    # 动作
    # ------------------------------------------------------------------ #
    def action_clear_screen(self) -> None:
        self._term().clear()

    async def action_quit(self) -> None:
        self.exit()

    def action_scroll_terminal(self, direction: int) -> None:
        """按页滚动面板（PageUp/PageDown）。

        若当前焦点在左侧目录树上，则滚动目录树；否则滚动右侧终端。
        两者都不受输入框焦点影响。
        """
        focused = self.focused
        if isinstance(focused, DirectoryTree):
            if direction < 0:
                focused.scroll_page_up()
            else:
                focused.scroll_page_down()
            return
        term = self._term()
        if direction < 0:
            term.scroll_page_up()
        else:
            term.scroll_page_down()


class BookmarkScreen(ModalScreen):
    """收藏夹弹窗：居中对话框，列出已收藏目录，可点击跳转或删除。

    设计为带边框的居中对话框（而非铺满全屏的 ModalScreen），避免空列表时
    整屏只剩被压暗的背景而看起来像「黑屏」。
    """

    CSS = """
    BookmarkScreen {
        align: center middle;
    }
    #bm_dialog {
        width: 80%;
        height: auto;
        max-height: 80%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #bm_title {
        height: auto;
        text-style: bold;
        padding: 0 0 1 0;
    }
    #bm_list {
        height: auto;
        max-height: 20;
        border: round $panel;
        padding: 0 1;
    }
    #bm_list > Horizontal {
        height: 3;
        margin: 0 0 1 0;
    }
    #bm_goto {
        width: 1fr;
        min-width: 0;
        text-align: left;
        content-align: left middle;
    }
    #bm_del {
        width: 10;
        margin-left: 1;
    }
    #bm_empty {
        height: auto;
        color: $text-muted;
        padding: 1 0;
    }
    #bm_close {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "关闭"),
    ]

    def __init__(self, dao: BookmarkDao) -> None:
        super().__init__()
        self.dao = dao

    def compose(self) -> ComposeResult:
        with Vertical(id="bm_dialog"):
            yield Label("收藏夹", id="bm_title")
            yield VerticalScroll(id="bm_list")
            yield Label("（暂无收藏，可在主界面点击「收藏」添加）", id="bm_empty")
            yield Button("关闭", id="bm_close", variant="primary")

    def on_mount(self) -> None:
        self._refresh()

    @staticmethod
    def _ellipsize(text: str, width: int = 50) -> str:
        """路径过长时截断并加省略号，避免按钮换行导致列表项过高。"""
        if len(text) <= width:
            return text
        return text[: width - 1] + "…"

    def _refresh(self) -> None:
        list_view = self.query_one("#bm_list", VerticalScroll)
        list_view.remove_children()
        items = self.dao.all()
        # 无收藏时显示提示，避免整块空白被误认为黑屏
        self.query_one("#bm_empty", Label).display = not bool(items)
        for bm in items:
            # 按钮显示省略后的路径，完整路径仍保存在 bm_path 供跳转使用；
            # 跳转按钮占满剩余宽度（width: 1fr），删除按钮自然靠右对齐
            goto = Button(self._ellipsize(bm.path), id="bm_goto")
            setattr(goto, "bm_path", bm.path)
            delete = Button("删除", id="bm_del", variant="error")
            setattr(delete, "bm_path", bm.path)
            list_view.mount(Horizontal(goto, delete))

    def action_close(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button
        if btn.id == "bm_close":
            self.dismiss(None)
            return
        path = getattr(btn, "bm_path", None)
        if btn.id == "bm_goto" and path is not None:
            event.stop()
            self.dismiss(path)
        elif btn.id == "bm_del" and path is not None:
            event.stop()
            self.dao.remove(path)
            self._refresh()


def main() -> None:
    parser = argparse.ArgumentParser(description="基于 Textual 的双栏终端")
    parser.add_argument("--path", default=".", help="初始工作目录（默认当前目录）")
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES,
                        help="终端历史最大行数（上下文上限，防止内存过大），默认 5000")
    args = parser.parse_args()

    start = args.path if os.path.isdir(args.path) else os.getcwd()
    DuckShellApp(start_path=start, max_lines=args.max_lines).run()


if __name__ == "__main__":
    main()
