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

from rich.text import Text

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DirectoryTree, RichLog, Input, Static, Header, Footer


DEFAULT_MAX_LINES = 5000

# ------------------------------------------------------------------ #
# 目录树扩展：在首行注入虚拟「返回上级目录」节点
# ------------------------------------------------------------------ #
class _UpEntry:
    """虚拟「返回上级目录」节点的数据：携带上层目录路径，使 DirectoryTree
    的现有逻辑把它当作普通目录处理（选择即触发 cd 到上层）。"""

    def __init__(self, path) -> None:
        self.path = path


class DuckDirTree(DirectoryTree):
    """在标准目录树顶部（首行）注入一个虚拟的「返回上级目录」节点。

    该节点携带上层目录路径，点击后由 DirectoryTree 内置的目录选择逻辑触发
    DirectorySelected（上层目录），应用层据此 cd ..；其余行为与 DirectoryTree 完全一致。
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # 隐藏根目录自身，使目录项（含虚拟节点）直接作为首行展示
        self.show_root = False

    def _populate_node(self, node: "TreeNode", content) -> None:  # noqa: F821
        # 先填充真实目录项
        super()._populate_node(node, content)
        # 仅在根节点（当前工作目录）的首行插入虚拟「返回上级目录」
        # 其数据携带上层目录路径，故会被当作普通目录处理 -> 触发 cd ..
        if node is self.root:
            parent = self.PATH(os.path.dirname(str(self.path)))
            node.add_leaf("[返回上级目录]", data=_UpEntry(parent), before=0)

    def render_label(self, node: "TreeNode", base_style, style) -> Text:  # noqa: F821
        if isinstance(node.data, _UpEntry):
            t = Text()
            t.append("↩ ", style="bold")
            t.append("[返回上级目录]", style="bold")
            t.stylize(base_style)
            return t
        return super().render_label(node, base_style, style)

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


class DuckShellApp(App):
    TITLE = "duck-shell"
    SUB_TITLE = "双栏终端"

    CSS = """
    #sidebar {
        width: 32%;
    }
    #tree {
        height: 1fr;
        border: round $accent;
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
    ]

    def __init__(self, start_path: str = ".", max_lines: int = DEFAULT_MAX_LINES):
        super().__init__()
        self.cwd: str = os.path.abspath(start_path)
        # 子进程环境（继承当前环境变量，命令执行时可继续累积修改）
        self.env: dict = dict(os.environ)
        self.max_lines: int = max_lines
        self.busy: bool = False

    # ------------------------------------------------------------------ #
    # 布局
    # ------------------------------------------------------------------ #
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                # 目录树首行即虚拟「返回上级目录」节点（由 DuckDirTree 注入）
                yield DuckDirTree(self.cwd, id="tree")
            with Vertical(id="rightcol"):
                yield RichLog(id="terminal",
                              max_lines=self.max_lines,
                              wrap=True,
                              highlight=False,
                              markup=False)
                with Vertical(id="input_area"):
                    yield Static(self._prompt_text(), id="prompt")
                    yield Input(id="cmdline", placeholder="输入命令，回车执行")
        yield Footer()

    # ------------------------------------------------------------------ #
    # 辅助
    # ------------------------------------------------------------------ #
    def _prompt_text(self) -> str:
        return self.cwd + "> "

    def _term(self) -> RichLog:
        return self.query_one("#terminal", RichLog)

    def _write(self, text: str) -> None:
        self._term().write(text)

    def on_mount(self) -> None:
        self._write("duck-shell 已启动。\n")
        self._write("左侧点击目录可切换右侧工作目录；点击目录树首行的 [返回上级目录] 可回到上层目录；\n")
        self._write("输入 exit 退出；Ctrl+L 清屏；交互式命令（python/vim/top…）自动交接屏幕控制权。\n\n")
        self.query_one("#cmdline", Input).focus()

    # ------------------------------------------------------------------ #
    # 目录树联动
    # ------------------------------------------------------------------ #
    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        if event.path is None:
            return
        self._change_dir(str(event.path))

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self._write("[文件] %s\n" % str(event.path))

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

    # ------------------------------------------------------------------ #
    # 命令输入与执行
    # ------------------------------------------------------------------ #
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.busy:
            return
        cmd = event.value.strip()
        self.query_one("#cmdline", Input).value = ""
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
                self._write("\n[退出码 %d]\n" % proc.returncode)
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

    def action_quit(self) -> None:
        self.exit()


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
