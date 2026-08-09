# -*- coding: utf-8 -*-
"""
Duck Git — 基于 prompt-toolkit 的 git 工具启动器

本身不执行任何 git 操作, 仅以列表形式汇总常用的 git 子命令与本项目自带的
git 类小工具; 选中某项后退出当前界面, 在终端中启动对应工具, 工具退出后再
回到本列表。

用法:
  duck-git                启动 git 工具列表
  duck-git -h | --help    显示本帮助

列表项分类:
  [git]   直接启动 git 子命令 (status / log / branch / diff / fetch ...)
  [tool]  启动 duck_rush/git 下的 git 小工具脚本 (git-push-all 等)
  [tui]   启动交互式 TUI 工具 (duck-git-log-tui / duck-git-diff-tui)

快捷键:
  ↑/↓       在列表内移动
  Enter      启动选中的工具 (退出后返回本列表)
  q / Ctrl-C 退出启动器
"""

import os
import sys
import subprocess
import argparse
from dataclasses import dataclass
from typing import List, Optional, Tuple

from prompt_toolkit import Application
from prompt_toolkit.widgets import RadioList, Frame
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings


GIT_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass
class ToolEntry:
    """列表中的一条 git 工具/操作。"""
    name: str                       # 列表展示名
    desc: str                       # 列表副标题
    command: str = ""               # 在终端中执行的外命令


def script_path(name: str) -> str:
    return os.path.join(GIT_DIR, name)


def build_tools() -> List[ToolEntry]:
    """构造左侧列表的数据源。"""
    tools: List[ToolEntry] = []

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
            name="[git] " + name, desc=desc,
            command="git " + subprocess.list2cmdline(args),
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
            name="[tool] " + name, desc=desc,
            command=f'{sys.executable} "{path}"',
        ))

    # ---- 交互式 TUI 工具 ----
    tui_tools = [
        ("duck-git-log-tui", "提交历史三栏查看器"),
        ("duck-git-diff-tui", "工作区改动查看器"),
    ]
    for name, desc in tui_tools:
        path = script_path(name + ".py")
        tools.append(ToolEntry(
            name="[tui] " + name, desc=desc,
            command=f'{sys.executable} "{path}"',
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


def build_app(tools: List[ToolEntry]) -> Application:
    """构造启动器界面。"""
    values = [(tool.command, f"{tool.name}  {tool.desc}") for tool in tools]
    radio = RadioList(values, default=tools[0].command)

    branch = find_current_branch()
    repo = find_repo_root() or os.getcwd()
    title = f"Duck Git 启动器  ·  {repo}  ({branch})"

    kb = KeyBindings()

    @kb.add("enter", eager=True)
    def _launch(event) -> None:
        radio._handle_enter()
        event.app.exit(result=radio.current_value)

    @kb.add("q")
    @kb.add("c-c")
    def _quit(event) -> None:
        event.app.exit(result=None)

    return Application(
        layout=Layout(Frame(radio, title=title)),
        key_bindings=kb,
        full_screen=True,
    )


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="基于 prompt-toolkit 的 git 工具启动器(列表选择, 退出后返回)",
        add_help=True,
    )
    parser.parse_args()

    tools = build_tools()
    # 循环: 启动器退出后若需启动某工具, 则在终端执行之, 完成后重新进入启动器
    while True:
        result: object = build_app(tools).run()
        if isinstance(result, str) and result:
            os.system(result)
            continue
        break


if __name__ == "__main__":
    main()
