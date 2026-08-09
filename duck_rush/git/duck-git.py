# -*- coding: utf-8 -*-
"""
Duck Git — 基于 Textual 的 git 工具入口

左侧以列表形式汇总常用的 git 操作与本项目自带的 git 类小工具,
右侧面板显示选中工具的运行结果, 通过 ↑/↓ 移动、Enter 运行。

用法:
  duck-git                启动 git 工具导航
  duck-git -h | --help    显示本帮助

列表项分类:
  [git]   直接执行 git 子命令 (status / log / branch / diff / fetch ...)
  [tool]  运行 duck_rush/git 下的 git 小工具脚本 (git-push-all 等)
  [tui]   启动交互式 TUI 工具 (duck-git-log-tui / duck-git-diff-tui),
          选中后会退出当前界面并在终端中启动该工具

快捷键:
  ↑/↓       在列表内移动
  Enter      运行选中的工具
  q          退出
"""

import os
import sys
import subprocess
import argparse
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, RichLog
from textual.containers import Horizontal


GIT_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass
class ToolEntry:
    """列表中的一条 git 工具/操作。"""
    name: str                       # 列表展示名
    desc: str                       # 列表副标题
    kind: str                       # "git" | "tool" | "tui"
    args: List[str] = field(default_factory=list)   # git 子命令参数
    command: str = ""               # tool/tui 模式下待执行的脚本路径


def script_path(name: str) -> str:
    return os.path.join(GIT_DIR, name)


def build_tools() -> List[ToolEntry]:
    """构造左侧列表的数据源。"""
    tools: List[ToolEntry] = []

    # ---- 直接执行 git 子命令 ----
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
        tools.append(ToolEntry(name="[git] " + name, desc=desc,
                               kind="git", args=args))

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
        tools.append(ToolEntry(name="[tool] " + name, desc=desc,
                               kind="tool", command=script_path(name + ".py")))

    # ---- 交互式 TUI 工具 ----
    tui_tools = [
        ("duck-git-log-tui", "提交历史三栏查看器"),
        ("duck-git-diff-tui", "工作区改动查看器"),
    ]
    for name, desc in tui_tools:
        tools.append(ToolEntry(name="[tui] " + name, desc=desc,
                               kind="tui", command=script_path(name + ".py")))

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


class ToolListItem(ListItem):
    """携带 ToolEntry 数据的列表项。"""

    def __init__(self, tool: ToolEntry, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tool = tool


APP_CSS = """
#tool-list {
    width: 42;
    height: 1fr;
    border: round $primary;
}
#output {
    width: 1fr;
    height: 1fr;
    border: round $primary;
}
ListItem:hover {
    background: $boost;
}
"""


class DuckGitApp(App):
    CSS = APP_CSS
    BINDINGS = [
        ("q", "quit", "退出"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.tools: List[ToolEntry] = build_tools()
        self.repo_root: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ListView(id="tool-list")
            yield RichLog(id="output", highlight=False, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Duck Git"
        self.repo_root = find_repo_root()
        branch = find_current_branch()
        repo = self.repo_root or os.getcwd()
        try:
            self.sub_title = f"{repo}  ({branch})"
        except Exception:
            pass

        list_view = self.query_one("#tool-list", ListView)
        for tool in self.tools:
            list_view.append(
                ToolListItem(
                    tool,
                    Label(tool.name),
                    Label(tool.desc, classes="tool-desc"),
                )
            )
        self.query_one(RichLog).write(
            "↑/↓ 选择, Enter 运行选中的 git 工具。右侧显示运行结果。")
        list_view.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        assert isinstance(event.item, ToolListItem)
        tool = event.item.tool
        if tool.kind == "tui":
            # 交互式 TUI 需要独占终端, 退出当前界面后再在外部启动
            self.exit(result=("launch", tool.command))
            return
        log = self.query_one(RichLog)
        self.run_worker(lambda: self._run_tool(log, tool), exclusive=True, thread=True)

    def _run_tool(self, log: RichLog, tool: ToolEntry) -> None:
        """在线程 worker 中执行命令, 通过 call_from_thread 把输出写回主线程。"""
        self.call_from_thread(log.clear)

        if tool.kind == "git":
            display = "git " + " ".join(tool.args)
            cmd: List[str] = ["git"] + tool.args
            cwd = self.repo_root or "."
        else:  # tool
            display = f"python {os.path.basename(tool.command)}"
            cmd = [sys.executable, tool.command]
            cwd = "."

        self.call_from_thread(log.write, f"$ {display}\n")
        try:
            proc = subprocess.Popen(
                cmd, cwd=cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace",
            )
            assert proc.stdout is not None
            for raw in proc.stdout:
                self.call_from_thread(log.write, raw.rstrip("\n"))
            proc.wait()
            self.call_from_thread(log.write, f"\n[exit code: {proc.returncode}]")
        except Exception as e:
            self.call_from_thread(log.write, f"\n执行失败: {e}")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="基于 Textual 的 git 工具入口(列表选择运行)",
        add_help=True,
    )
    parser.parse_args()

    result: object = DuckGitApp().run()
    if isinstance(result, tuple) and len(result) == 2 and result[0] == "launch":
        command = result[1]
        assert isinstance(command, str)
        os.system(command)


if __name__ == "__main__":
    main()
