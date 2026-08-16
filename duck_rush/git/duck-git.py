# -*- coding: utf-8 -*-
"""
Duck Git — 基于 prompt-toolkit 的 git 工具启动器 (样式参考 duck-fav)

本身不执行任何 git 操作, 仅以列表形式汇总常用的 git 子命令与本项目自带的
git 类小工具; 选中某项后在终端中启动对应工具。

用法:
  duck-git                启动 git 工具列表
  duck-git -h | --help    显示本帮助

列表项分类 (顺序: tui → tool → git):
  [tui]   启动交互式 TUI 工具 (duck-git-log-tui / duck-git-diff-tui)
  [tool]  启动 duck_rush/git 下的 git 小工具脚本 (git-push-all 等)
  [git]   直接启动 git 子命令 (status / log / branch / diff / fetch ...)

快捷键(列表界面):
  ↑/↓       在列表内移动
  Enter      启动选中的工具 (结束后自动回到菜单, 不清屏)
  q / Esc    退出启动器 (列表底部也有 [quit] 退出项可 Enter 选中)
"""

import os
import sys
import subprocess
import argparse
from dataclasses import dataclass
from typing import List, Optional

from prompt_toolkit import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style


GIT_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass
class ToolEntry:
    """列表中的一条 git 工具/操作。"""
    name: str                       # 列表展示名, 带 [git]/[tool]/[tui] 前缀
    desc: str                       # 列表副标题
    kind: str                       # "git" | "tool" | "tui" (决定退出逻辑)
    command: str = ""               # 在终端中执行的外命令


def script_path(name: str) -> str:
    return os.path.join(GIT_DIR, name)


def build_tools() -> List[ToolEntry]:
    """构造左侧列表的数据源 (顺序: tui → tool → git)。"""
    tools: List[ToolEntry] = []

    # ---- 交互式 TUI 工具 ----
    tui_tools = [
        ("duck-git-log-tui", "提交历史三栏查看器"),
        ("duck-git-diff-tui", "工作区改动查看器"),
    ]
    for name, desc in tui_tools:
        path = script_path(name + ".py")
        tools.append(ToolEntry(
            name="[tui] " + name, desc=desc, kind="tui",
            command=f'{sys.executable} "{path}"',
        ))

    # ---- 本项目的 git 小工具脚本 ----
    tool_scripts = [
        ("git-count-lines", "统计各作者提交行数"),
        ("git-push-all", "推送到所有远端"),
        ("git-pull-remote", "拉取当前分支远端更新"),
        ("git-pull-force", "强制从 origin/master 同步"),
        ("git-checkout", "checkout 指定分支"),
        ("git-delete-other-branches", "删除其他本地分支"),
        ("git-try-fix", "清理缓存 / 删除 lock 文件"),
    ]
    for name, desc in tool_scripts:
        path = script_path(name + ".py")
        tools.append(ToolEntry(
            name="[tool] " + name, desc=desc, kind="tool",
            command=f'{sys.executable} "{path}"',
        ))

    # ---- 直接启动 git 子命令 ----
    git_ops = [
        ("status", "查看工作区状态", ["status"]),
        ("log", "最近提交记录 (oneline)", ["log", "--oneline", "-n", "30"]),
        ("branch", "本地与远端分支", ["branch", "-a"]),
        ("diff", "未暂存的改动", ["diff"]),
        ("diff --cached", "已暂存的改动", ["diff", "--cached"]),
        ("stash list", "暂存栈列表", ["stash", "list"]),
        ("remote -v", "远端仓库", ["remote", "-v"]),
        ("fetch --all", "抓取所有远端", ["fetch", "--all"]),
        ("pull", "拉取当前分支", ["pull"]),
        ("push", "推送当前分支", ["push"]),
    ]
    for name, desc, args in git_ops:
        tools.append(ToolEntry(
            name="[git] " + name, desc=desc, kind="git",
            command="git " + subprocess.list2cmdline(args),
        ))

    # ---- 退出选项 (选中即退出; 也可按 q/Esc) ----
    tools.append(ToolEntry(
        name="[quit] 退出", desc="退出启动器 (或按 q/Esc)", kind="quit",
        command="",
    ))

    return tools


def find_repo_root() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, encoding="utf-8", errors="replace", check=True,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def find_current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, encoding="utf-8", errors="replace",
        )
        return result.stdout.strip() or "(未知)"
    except Exception:
        return "(未知)"


_STYLE = Style.from_dict(
    {
        "title": "ansibrightgreen bold",
        "git": "ansibrightcyan",
        "tool": "ansibrightblue",
        "tui": "ansibrightyellow",
        "quit": "ansibrightmagenta",
        "selected": "reverse",
        "hint": "ansigray",
    }
)


class GitLauncherApp:
    """基于 prompt_toolkit 的 git 工具选择器 (样式参考 duck-fav)。"""

    def __init__(self, tools: List[ToolEntry]) -> None:
        self.tools: List[ToolEntry] = tools
        self.index: int = 0
        self.result: Optional[str] = None  # 选中的命令; None 表示取消退出
        self._pt_app: Optional[Application] = None
        self._pt_app = self._build()

    def _get_text(self) -> FormattedText:
        ft = FormattedText()
        repo = find_repo_root() or os.getcwd()
        branch = find_current_branch()
        ft.append(
            ("class:title",
             "Duck Git 启动器 — %s (%s)\n\n" % (repo, branch))
        )

        # 视口: 内容超过一屏时围绕当前选中项居中显示
        avail = 1 << 30
        try:
            from prompt_toolkit.application import get_app
            avail = max(1, get_app().output.get_size().rows - 4)
        except Exception:  # noqa: 非运行期(如单测)退化为全部显示
            pass

        n = len(self.tools)
        top = 0
        if n > avail:
            top = max(0, min(self.index - avail // 2, n - avail))
        for i in range(top, min(n, top + avail)):
            e = self.tools[i]
            style = ("class:selected," if i == self.index else "class:") + e.kind
            marker = "> " if i == self.index else "  "
            ft.append((style, marker + e.name + "  " + e.desc))
            ft.append(("", "\n"))
        if n > avail:
            ft.append(("class:hint", "... 更多项, 用 ↑/↓ 浏览 ...\n"))
        ft.append(("class:hint",
                   "\n↑/↓ 选择, Enter 启动, q/Esc 退出 (结束后自动回到菜单)"))
        return ft

    def _emit(self, value: Optional[str]) -> None:
        self.result = value
        if self._pt_app is not None:
            self._pt_app.exit()

    def _launch(self) -> None:
        if self.tools:
            e = self.tools[self.index]
            # 空命令(如 [quit] 退出项)或选中退出项时, 等同取消退出
            if e.kind == "quit" or not e.command:
                self._emit(None)
            else:
                self._emit(e.command)

    def _build(self) -> Application:
        bindings = KeyBindings()

        @bindings.add("up")
        def _up(event: object) -> None:  # noqa: 参数由 prompt_toolkit 注入
            if self.tools:
                self.index = (self.index - 1) % len(self.tools)

        @bindings.add("down")
        def _down(event: object) -> None:  # noqa
            if self.tools:
                self.index = (self.index + 1) % len(self.tools)

        @bindings.add("enter")
        def _enter(event: object) -> None:  # noqa
            self._launch()

        @bindings.add("q")
        @bindings.add("escape")
        def _quit(event: object) -> None:  # noqa: 退出(未选择)
            self._emit(None)

        @bindings.add("c-c")
        def _ctrl_c(event: object) -> None:  # noqa: Ctrl+C 不崩溃, 等同退出
            self._emit(None)

        control = FormattedTextControl(self._get_text, focusable=True)
        layout = Layout(Window(control))
        return Application(
            layout=layout,
            key_bindings=bindings,
            style=_STYLE,
            full_screen=False,
            mouse_support=False,
        )

    def run(self) -> None:
        assert self._pt_app is not None
        self._pt_app.run()


def main() -> None:
    # -h/--help 必须无副作用, 放最开头直接退出
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="基于 prompt-toolkit 的 git 工具启动器(列表选择, 结束后回到菜单)",
        add_help=True,
    )
    parser.parse_args()

    tools = build_tools()
    # 选中工具后在终端启动; 结束后不清屏, 直接回到菜单继续选择, q/Esc 退出
    while True:
        app = GitLauncherApp(tools)
        app.run()
        res = app.result
        if not (isinstance(res, str) and res):
            break  # q/Esc 退出
        os.system(res)


if __name__ == "__main__":
    main()
