# -*- coding: utf-8 -*-
"""
Git Diff TUI — 基于 Textual 的 git diff 查看器

左右分栏布局: 左侧为改动文件列表, 右侧为选中文件的 diff 内容。
支持查看工作区改动、已暂存改动、某次提交、或任意两个引用之间的 diff。

用法:
  duck-git-diff-tui                查看未暂存的工作区改动 (git diff)
  duck-git-diff-tui --staged       查看已暂存改动 (git diff --cached)
  duck-git-diff-tui --commit <sha> 查看某次提交的改动
  duck-git-diff-tui <a> <b>        查看两个引用之间的改动 (git diff <a> <b>)
  duck-git-diff-tui <ref>          等价 --commit <ref>

快捷键:
  ↑/↓   切换文件
  Enter 查看选中文件
  s     将选中文件加入暂存区 (git add)
  u     将选中文件移出暂存区 (git restore --staged)
  r     刷新
  q     退出
"""

import sys
import argparse
import subprocess
from typing import Callable, List, NamedTuple, Optional

from rich.text import Text

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, RichLog
from textual.containers import Horizontal

from duck_utils.os_util import emoji_supported


# ============================================================
# 数据模型与 git 命令封装
# ============================================================

class FileEntry(NamedTuple):
    status: str
    path: str
    old_path: Optional[str]
    untracked: bool = False
    staged: bool = False


class DiffContext:
    """描述一次 diff 的来源, 以及获取文件列表 / 单个文件 diff 的命令。"""

    def __init__(self, name: str, list_command: List[str],
                 diff_command_builder: Callable[[str], List[str]],
                 strip_header: bool = False,
                 include_untracked: bool = False,
                 staged_view: bool = False) -> None:
        self.name = name
        self.list_command = list_command
        self._build_diff = diff_command_builder
        self.strip_header = strip_header
        self.include_untracked = include_untracked
        self.staged_view = staged_view

    def diff_command(self, path: str) -> List[str]:
        return self._build_diff(path)


# 状态首字母 -> 颜色
STATUS_STYLE = {
    "A": "green",     # Added
    "D": "red",       # Deleted
    "M": "yellow",    # Modified
    "R": "blue",      # Renamed
    "C": "blue",      # Copied
    "T": "magenta",   # Type changed
    "U": "bold red",  # Unmerged
}


def status_letter(status: str) -> str:
    return status[0] if status else "?"


def status_style(status: str) -> str:
    return STATUS_STYLE.get(status_letter(status), "white")


def parse_name_status(output: str) -> List[FileEntry]:
    """解析 `git diff --name-status` / `git show --name-status` 的输出。"""
    files: List[FileEntry] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        if status.startswith(("R", "C")) and len(parts) >= 3:
            # 重命名/复制: 旧路径 -> 新路径, diff 以新路径为准
            files.append(FileEntry(status=status, path=parts[2], old_path=parts[1]))
        else:
            files.append(FileEntry(status=status, path=parts[1], old_path=None))
    return files


def strip_show_header(output: str) -> str:
    """去掉 `git show` 的提交信息头, 只保留 diff 部分。"""
    lines = output.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("diff --git"):
            return "\n".join(lines[i:])
    return output


def render_diff(diff: str) -> Text:
    """把统一格式 diff 渲染为带颜色的 Rich Text。"""
    text = Text()
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            text.append(line + "\n", style="green")
        elif line.startswith("-") and not line.startswith("---"):
            text.append(line + "\n", style="red")
        elif line.startswith("@@"):
            text.append(line + "\n", style="bold cyan")
        elif line.startswith(("diff --git", "index ", "---", "+++")):
            text.append(line + "\n", style="dim")
        else:
            text.append(line + "\n")
    return text


def find_repo_root() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, encoding="utf-8", errors="replace", check=True,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def build_context(args: argparse.Namespace) -> DiffContext:
    if args.commit:
        sha = args.commit
        return DiffContext(
            name="commit %s" % sha,
            list_command=["git", "show", "--name-status", "--format=", sha],
            diff_command_builder=lambda p: ["git", "show", sha, "--", p],
            strip_header=True,
        )
    if len(args.refs) == 2:
        a, b = args.refs
        return DiffContext(
            name="%s..%s" % (a, b),
            list_command=["git", "diff", "--name-status", a, b],
            diff_command_builder=lambda p: ["git", "diff", a, b, "--", p],
        )
    if len(args.refs) == 1:
        sha = args.refs[0]
        return DiffContext(
            name="commit %s" % sha,
            list_command=["git", "show", "--name-status", "--format=", sha],
            diff_command_builder=lambda p: ["git", "show", sha, "--", p],
            strip_header=True,
        )
    if args.staged:
        return DiffContext(
            name="staged",
            list_command=["git", "diff", "--cached", "--name-status"],
            diff_command_builder=lambda p: ["git", "diff", "--cached", "--", p],
            staged_view=True,
        )
    return DiffContext(
        name="unstaged",
        list_command=["git", "diff", "--name-status"],
        diff_command_builder=lambda p: ["git", "diff", "--", p],
        include_untracked=True,
    )


# ============================================================
# TUI 应用
# ============================================================

APP_CSS = """
ListView {
    width: 36;
    height: 1fr;
    border: round $primary;
}
#diff-view {
    width: 1fr;
    height: 1fr;
    border: round $primary;
}
ListItem:hover {
    background: $boost;
}
"""


class GitDiffTUI(App):
    CSS = APP_CSS
    BINDINGS = [
        ("s", "stage", "暂存"),
        ("u", "unstage", "取消暂存"),
        ("q", "quit", "退出"),
        ("r", "refresh", "刷新"),
    ]

    def __init__(self, ctx: DiffContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.files: List[FileEntry] = []
        self.repo_root: Optional[str] = None
        self.use_emoji: bool = emoji_supported()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ListView(id="file-list")
            yield RichLog(id="diff-view", auto_scroll=False, highlight=False)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Git Diff TUI"
        self._load()
        self.query_one(ListView).focus()

    def _item_text(self, f: FileEntry) -> Text:
        label = Text()
        if f.staged:
            mark = "✔ " if self.use_emoji else "* "
            label.append(mark, style="green")
        else:
            label.append("  ", style="dim")
        label.append("[%s] " % status_letter(f.status), style=status_style(f.status))
        label.append(f.path)
        if f.staged:
            label.append("  [staged]", style="green")
        return label

    def _make_item(self, f: FileEntry) -> ListItem:
        return ListItem(Label(self._item_text(f)))

    def _load(self) -> None:
        log = self.query_one(RichLog)
        repo = find_repo_root()
        if repo is None:
            log.clear()
            log.write(Text("当前目录不是 git 仓库", style="red"))
            return
        self.repo_root = repo
        try:
            result = subprocess.run(
                self.ctx.list_command, cwd=repo,
                capture_output=True, encoding="utf-8", errors="replace", check=True,
            )
            output = result.stdout
        except Exception as e:
            log.clear()
            log.write(Text("获取文件列表失败: %s" % e, style="red"))
            return
        base = parse_name_status(output)
        if self.ctx.staged_view:
            # 已暂存视图: 列表项全部标记为 staged
            self.files = [FileEntry(status=f.status, path=f.path, old_path=f.old_path,
                                    untracked=f.untracked, staged=True)
                          for f in base]
        else:
            # 默认(工作区)视图: 同时展示 未暂存 + 已暂存 改动, 已暂存项标记 staged=True,
            # 这样暂存后在别处重新打开本工具, 文件仍保留在列表中(只更新状态)。
            cached_out = subprocess.run(
                ["git", "diff", "--cached", "--name-status"], cwd=repo,
                capture_output=True, encoding="utf-8", errors="replace",
            ).stdout or ""
            merged: dict = {}
            for entry in parse_name_status(cached_out):
                merged[entry.path] = FileEntry(status=entry.status, path=entry.path,
                                               old_path=entry.old_path, untracked=False,
                                               staged=True)
            for entry in base:
                if entry.path in merged:
                    # 已暂存之上又有未暂存改动, 仍视为 staged
                    merged[entry.path] = FileEntry(status=entry.status, path=entry.path,
                                                   old_path=entry.old_path, untracked=False,
                                                   staged=True)
                else:
                    merged[entry.path] = FileEntry(status=entry.status, path=entry.path,
                                                   old_path=entry.old_path, untracked=False,
                                                   staged=False)
            self.files = list(merged.values())
            if self.ctx.include_untracked:
                # 未跟踪的新文件不在 git diff 中, 需额外从 git status 获取, 以便可暂存
                try:
                    st = subprocess.run(
                        ["git", "status", "--porcelain"], cwd=repo,
                        capture_output=True, encoding="utf-8", errors="replace",
                    ).stdout
                    for line in st.splitlines():
                        if line[:2] == "??":
                            self.files.append(FileEntry(
                                status="??", path=line[3:].strip(),
                                old_path=None, untracked=True))
                except Exception:
                    pass
        list_view = self.query_one(ListView)
        list_view.clear()
        for f in self.files:
            list_view.append(self._make_item(f))
        self.sub_title = "%s · %d files" % (self.ctx.name, len(self.files))
        if self.files:
            self._select(index=0)
        else:
            log.clear()
            log.write(Text("没有改动 (No changes)", style="yellow"))

    def _select(self, path: Optional[str] = None, index: Optional[int] = None) -> None:
        """选中文件列表中的某一项并刷新右侧 diff; 优先按路径, 其次按索引。"""
        list_view = self.query_one(ListView)
        if not self.files:
            return
        if path is not None:
            for i, f in enumerate(self.files):
                if f.path == path:
                    list_view.index = i
                    self._show_diff(i)
                    return
        if index is not None:
            idx = max(0, min(index, len(self.files) - 1))
            list_view.index = idx
            self._show_diff(idx)
            return
        list_view.index = 0
        self._show_diff(0)

    def _show_diff(self, index: Optional[int]) -> None:
        if index is None or index < 0 or index >= len(self.files):
            return
        assert self.repo_root is not None
        f = self.files[index]
        if f.untracked:
            cmd = ["git", "diff", "--no-index", "--", "/dev/null", f.path]
        elif self.ctx.staged_view and not f.staged:
            # 在已暂存视图里被取消暂存的文件, 显示工作区 diff
            cmd = ["git", "diff", "--", f.path]
        elif f.staged:
            cmd = ["git", "diff", "--cached", "--", f.path]
        else:
            cmd = self.ctx.diff_command(f.path)
        try:
            result = subprocess.run(
                cmd, cwd=self.repo_root,
                capture_output=True, encoding="utf-8", errors="replace",
            )
            output = result.stdout
        except Exception:
            output = ""
        if output is None:
            output = ""
        if self.ctx.strip_header:
            output = strip_show_header(output)
        log = self.query_one(RichLog)
        log.clear()
        stage_tag = "  [green]staged[/green]" if f.staged else ""
        log.write(Text.from_markup("[b]%s[/b]  [dim]%s[/dim]%s\n"
                                   % (f.path, f.status, stage_tag)))
        log.write(render_diff(output))
        log.scroll_home()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        idx = event.list_view.index
        if idx is not None:
            self._show_diff(idx)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is not None:
            self._show_diff(idx)

    def action_refresh(self) -> None:
        self._load()

    def action_stage(self) -> None:
        self._git_update("stage")

    def action_unstage(self) -> None:
        self._git_update("unstage")

    def _entry_from_status(self, path: str) -> Optional[FileEntry]:
        """根据 git status 重新计算某路径的条目(已暂存/未暂存/未跟踪)。"""
        try:
            out = subprocess.run(
                ["git", "status", "--porcelain", "--", path], cwd=self.repo_root,
                capture_output=True, encoding="utf-8", errors="replace",
            ).stdout
        except Exception:
            return None
        line = ""
        for ln in out.splitlines():
            if ln.strip():
                line = ln
                break
        if not line or len(line) < 2:
            return None
        x, y = line[0], line[1]
        if x == "?" or y == "?":
            # 未跟踪
            return FileEntry(status="??", path=path, old_path=None,
                             untracked=True, staged=False)
        if x != " ":
            # 索引(暂存区)有改动 -> 已暂存, 以索引状态展示
            return FileEntry(status=x, path=path, old_path=None, staged=True)
        # 仅工作区有改动
        return FileEntry(status=y, path=path, old_path=None, staged=False)

    def _refresh_entry(self, idx: int) -> None:
        """就地刷新第 idx 个文件的(暂存)状态, 不把它从列表移除;
        若文件已无任何改动(如暂存后与 HEAD 一致)则移除。"""
        if idx < 0 or idx >= len(self.files):
            return
        f = self.files[idx]
        new_entry = self._entry_from_status(f.path)
        list_view = self.query_one(ListView)
        if new_entry is None:
            self.files.pop(idx)
            try:
                list_view.children[idx].remove()
            except Exception:
                pass
            if self.files:
                self._select(index=max(0, min(idx, len(self.files) - 1)))
            else:
                self.query_one(RichLog).clear()
                self.query_one(RichLog).write(
                    Text("没有改动 (No changes)", style="yellow"))
            return
        self.files[idx] = new_entry
        try:
            item = list_view.children[idx]
            item.query_one(Label).update(self._item_text(new_entry))
        except Exception:
            pass
        self._show_diff(idx)

    def _git_update(self, op: str) -> None:
        """对当前选中文件执行暂存 / 取消暂存, 就地更新其状态(文件保留在列表中)。"""
        list_view = self.query_one(ListView)
        idx = list_view.index
        if idx is None or idx < 0 or idx >= len(self.files):
            self.notify("请先选择一个文件", severity="warning")
            return
        f = self.files[idx]
        if op == "unstage" and not f.staged:
            self.notify("文件尚未暂存, 无需取消暂存: %s" % f.path, severity="warning")
            return
        if op == "stage":
            cmd = ["git", "add", "--", f.path]
            verb = "已暂存"
        else:
            cmd = ["git", "restore", "--staged", "--", f.path]
            verb = "已取消暂存"
        try:
            subprocess.run(
                cmd, cwd=self.repo_root,
                capture_output=True, encoding="utf-8", errors="replace", check=True,
            )
            self.notify("%s: %s" % (verb, f.path))
        except Exception as e:
            self.notify("操作失败: %s" % e, severity="error")
            return
        self._refresh_entry(idx)


# ============================================================
# 入口
# ============================================================

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="duck-git-diff-tui",
        description="基于 Textual 的 git diff 查看器 (左: 文件列表, 右: diff 内容)",
    )
    parser.add_argument("--staged", "--cached", action="store_true",
                        help="查看已暂存(staged)的改动")
    parser.add_argument("--commit", "-c", metavar="SHA",
                        help="查看某次提交的改动(与该提交的父提交对比)")
    parser.add_argument("refs", nargs="*",
                        help="可选 1~2 个引用: 1 个表示提交(--commit), 2 个表示 git diff <a> <b>")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    GitDiffTUI(build_context(args)).run()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip() if __doc__ else "Usage: duck-git-diff-tui [options] [REF...]")
        sys.exit(0)
    main()
