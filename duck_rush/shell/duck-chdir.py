# -*- coding: utf-8 -*-
"""
duck-chdir —— 交互式目录 / 文件选择（prompt_toolkit 实现的纯选择器）。

只负责「选择」并返回结果，不调用任何外部命令（外部命令由调用方 duck-cli 负责）：

- 列出当前目录内容，列表顶部额外提供一个选项 [切换到当前目录]
- 列表底部提供 [退出] 选项
- 进入子目录、返回上级目录（..）
- 选定后把结果输出为一行（供调用方 duck-cli 解析）：
    dir  <绝对路径>    选择了某个目录 / 切换到当前目录
    file <绝对路径>    选择了一个文件
    exit               直接退出（未选择）

用法:
  duck-chdir [路径] [--result-file FILE] [-h]

说明:
  作为独立命令运行时，结果打印到 stdout；
  通过 --result-file 调用时（如 duck-cli 的 `cd` 无参），结果写入该文件。
"""
import argparse
import os
import sys
from dataclasses import dataclass
from typing import List, Optional

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style


SWITCH_CURRENT_LABEL = "[切换到当前目录]"
PARENT_LABEL = "..  上级目录"
EXIT_LABEL = "[退出]"

# 不同种类条目的样式类名
_CLASS_OF = {
    "current": "current",
    "parent": "parent",
    "dir": "dir",
    "file": "file",
    "exit": "exit",
}


@dataclass
class Entry:
    """列表中的一项：kind 区分特殊选项 / 目录 / 文件。"""

    kind: str          # "current" | "parent" | "dir" | "file" | "exit"
    path: str          # 绝对路径
    label: str         # 展示文本
    count: Optional[int] = None  # 仅目录：子项（文件+文件夹）数量


_STYLE = Style.from_dict(
    {
        "path": "ansibrightblue bold",
        "current": "ansigreen bold",
        "parent": "ansiyellow",
        "dir": "ansicyan",
        "file": "ansiwhite",
        "exit": "ansired",
        "count": "ansigray",
        "selected": "reverse",
        "toolbar": "ansigray",
    }
)


class ChdirApp:
    """基于 prompt_toolkit 的目录 / 文件选择器（纯选择，不调用外部命令）。"""

    def __init__(self, start_path: str, result_file: Optional[str] = None) -> None:
        self.cwd: str = os.path.abspath(start_path)
        self.result_file: Optional[str] = result_file
        self.entries: List[Entry] = []
        self.index: int = 0
        self.result: Optional[str] = None
        self._pt_app: Optional[Application] = None
        self._rebuild()
        self._pt_app = self._build()

    # ------------------------------------------------------------------ #
    # 列表构建
    # ------------------------------------------------------------------ #
    def _rebuild(self) -> None:
        """重新读取当前目录并填充列表。

        顺序： [切换到当前目录] -> (.. 上级目录) -> 目录 -> 文件 -> [退出]
        """
        entries: List[Entry] = [Entry("current", self.cwd, SWITCH_CURRENT_LABEL)]
        parent = os.path.dirname(self.cwd)
        if parent and parent != self.cwd and os.path.isdir(parent):
            entries.append(Entry("parent", parent, PARENT_LABEL))

        try:
            names = sorted(os.listdir(self.cwd))
        except OSError:
            names = []

        join = os.path.join
        dirs = [n for n in names if os.path.isdir(join(self.cwd, n))]
        files = [n for n in names if not os.path.isdir(join(self.cwd, n))]
        for n in dirs:
            dir_path = join(self.cwd, n)
            try:
                count = len(os.listdir(dir_path))
            except OSError:
                count = None
            entries.append(Entry("dir", dir_path, n + "/", count))
        for n in files:
            entries.append(Entry("file", join(self.cwd, n), n))
        entries.append(Entry("exit", self.cwd, EXIT_LABEL))

        self.entries = entries
        if self.index >= len(entries):
            self.index = 0

    # ------------------------------------------------------------------ #
    # 渲染
    # ------------------------------------------------------------------ #
    def _get_text(self) -> FormattedText:
        ft = FormattedText()
        ft.append(("class:path", "当前目录: " + self.cwd + "\n\n"))

        # 视口：内容超过一屏时，围绕当前选中项居中显示
        avail = 1 << 30
        try:
            from prompt_toolkit.application import get_app
            avail = max(1, get_app().output.get_size().rows - 3)
        except Exception:  # noqa: 非运行期（如单测）时退化为全部显示
            pass

        n = len(self.entries)
        top = 0
        if n > avail:
            top = max(0, min(self.index - avail // 2, n - avail))
        for i in range(top, min(n, top + avail)):
            e = self.entries[i]
            style = ("class:selected," if i == self.index else "class:") + _CLASS_OF[e.kind]
            marker = "> " if i == self.index else "  "
            ft.append((style, marker + e.label))
            # 目录：在名称后追加子项数量（文件+文件夹），灰色显示
            if e.kind == "dir" and e.count is not None:
                count_style = "class:count" + (",selected" if i == self.index else "")
                ft.append((count_style, " (%d)" % e.count))
            ft.append(("", "\n"))
        if n > avail:
            ft.append(("class:toolbar", "... 更多项，用 ↑/↓ 浏览 ...\n"))
        return ft

    # ------------------------------------------------------------------ #
    # 交互逻辑
    # ------------------------------------------------------------------ #
    def _go(self, path: str) -> None:
        if not os.path.isdir(path):
            return
        self.cwd = path
        self.index = 0
        self._rebuild()

    def _emit(self, line: str) -> None:
        """记录选择结果并退出 prompt_toolkit 应用。"""
        self.result = line
        if self._pt_app is not None:
            self._pt_app.exit()

    def _act(self, entry: Entry) -> None:
        if entry.kind == "current":
            self._emit("dir %s" % self.cwd)
        elif entry.kind == "file":
            self._emit("file %s" % entry.path)
        elif entry.kind == "exit":
            self._emit("exit")
        else:  # parent / dir：进入该目录（导航，非选择）
            self._go(entry.path)

    def _build(self) -> Application:
        bindings = KeyBindings()

        @bindings.add("up")
        def _up(event: object) -> None:  # noqa: 参数由 prompt_toolkit 注入
            if self.entries:
                self.index = (self.index - 1) % len(self.entries)

        @bindings.add("down")
        def _down(event: object) -> None:  # noqa
            if self.entries:
                self.index = (self.index + 1) % len(self.entries)

        @bindings.add("enter")
        def _enter(event: object) -> None:  # noqa
            if self.entries:
                self._act(self.entries[self.index])

        @bindings.add("backspace")
        def _back(event: object) -> None:  # noqa: 返回上级目录
            parent = os.path.dirname(self.cwd)
            if parent and parent != self.cwd:
                self._go(parent)

        @bindings.add("q")
        @bindings.add("escape")
        def _quit(event: object) -> None:  # noqa: 退出（未选择）
            self._emit("exit")

        @bindings.add("c-c")
        def _ctrl_c(event: object) -> None:  # noqa: Ctrl+C 不崩溃，等同退出
            self._emit("exit")

        control = FormattedTextControl(self._get_text, focusable=True)
        toolbar_text = FormattedText(
            [
                (
                    "class:toolbar",
                    "↑/↓ 选择   Enter 确认/进入目录   [切换到当前目录] 直接Enter确认当前目录"
                    "   Backspace 上级目录   q/Esc 退出",
                )
            ]
        )
        toolbar_control = FormattedTextControl(toolbar_text, focusable=False)
        layout = Layout(
            HSplit([Window(control), Window(toolbar_control, height=1)])
        )
        return Application(
            layout=layout,
            key_bindings=bindings,
            style=_STYLE,
            full_screen=True,
            mouse_support=False,
        )

    def run(self) -> None:
        assert self._pt_app is not None
        self._pt_app.run()


def _write_result(line: str, result_file: Optional[str]) -> None:
    """把选择结果输出（写文件或打印 stdout）。"""
    if result_file:
        try:
            with open(result_file, "w", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            sys.stderr.write("写入结果失败: %s\n" % e)
    else:
        print(line)


def main() -> None:
    # -h/--help 必须无副作用（不得执行选择、不写文件），放最开头直接退出
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", nargs="?", default=".",
                        help="起始目录（默认当前目录）")
    parser.add_argument("--result-file", default=None,
                        help="将选择结果写入该文件（供调用方读取）；不传则打印到 stdout")
    args = parser.parse_args()

    start = args.path if os.path.isdir(args.path) else os.getcwd()
    app = ChdirApp(start_path=start, result_file=args.result_file)
    try:
        app.run()
    except Exception as e:  # noqa: 异常通过退出码 + stderr 暴露给调用方
        sys.stderr.write("duck-chdir 异常: %s\n" % e)
        sys.exit(1)

    line = app.result if app.result is not None else "exit"
    _write_result(line, args.result_file)


if __name__ == "__main__":
    main()
