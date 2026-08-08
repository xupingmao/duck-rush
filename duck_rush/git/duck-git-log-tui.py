# -*- coding: utf-8 -*-
"""
Git Log TUI — 基于 Textual 的 git 提交历史查看器

三栏布局: 左侧为提交记录, 中间为选中提交改动的文件列表, 右侧为选中文件的 diff 内容。
提交记录会标注与远端是否同步 (已推送到远端 / 本地领先未推送 / 无远端跟踪分支)。

用法:
  duck-git-log-tui           查看当前分支的提交历史
  duck-git-log-tui <branch>  查看指定分支/引用的提交历史

选项:
  --date-format {absolute,relative}  时间显示格式 (默认 absolute 绝对时间)

快捷键:
  ↑/↓       在当前栏内上下移动
  ←/→       在 提交记录 / 文件列表 / diff 三栏之间切换焦点
  Enter     选中 (与 ↑/↓ 等价, 自动联动刷新)
  r         刷新 (重新读取提交/同步状态)
  q         退出

关于"是否和远端同步":
  以本地仓库的远端跟踪分支 (如 origin/master) 为基准: 某次提交只要存在于远端
  跟踪分支的提交集合中, 即视为已同步(已推送), 否则视为本地领先未推送。
  注意远端跟踪分支反映最近一次 fetch/pull 的状态, 若本地已 push 但未 fetch,
  可能短暂显示为"未推送"。
"""

import sys
import argparse
import subprocess
from typing import List, NamedTuple, Optional, Set, Tuple

from rich.text import Text

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, RichLog
from textual.containers import Horizontal


# ============================================================
# 数据模型
# ============================================================

class CommitEntry(NamedTuple):
    sha: str
    short: str
    author: str
    date: str
    subject: str
    synced: bool          # 是否与远端同步(已推送)
    sync_known: bool      # 是否存在远端跟踪分支(可判断同步状态)


class FileEntry(NamedTuple):
    status: str
    path: str
    old_path: Optional[str]


# 状态首字母 -> 颜色 (与 duck-git-diff-tui 保持一致)
STATUS_STYLE = {
    "A": "green",
    "D": "red",
    "M": "yellow",
    "R": "blue",
    "C": "blue",
    "T": "magenta",
    "U": "bold red",
}


def status_letter(status: str) -> str:
    return status[0] if status else "?"


def status_style(status: str) -> str:
    return STATUS_STYLE.get(status_letter(status), "white")


def parse_name_status(output: str) -> List[FileEntry]:
    """解析 `git diff-tree --name-status` / `git show --name-status` 的输出。"""
    files: List[FileEntry] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        if status.startswith(("R", "C")) and len(parts) >= 3:
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


# ============================================================
# TUI 应用
# ============================================================

APP_CSS = """
#commit-list {
    width: 46;
    height: 1fr;
    border: round $primary;
}
#file-list {
    width: 44;
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


class GitLogTUI(App):
    CSS = APP_CSS
    BINDINGS = [
        ("q", "quit", "退出"),
        ("r", "refresh", "刷新"),
        ("left", "focus_previous", "← 上一栏"),
        ("right", "focus_next", "→ 下一栏"),
    ]

    def __init__(self, ref: Optional[str] = None, date_format: str = "absolute") -> None:
        super().__init__()
        # ref 为 None 时表示当前 HEAD / 当前分支
        self.ref: Optional[str] = ref
        # 时间显示格式: "absolute" 绝对时间 / "relative" 相对时间
        self.date_format: str = date_format
        self.commits: List[CommitEntry] = []
        self.files: List[FileEntry] = []
        self.current_commit: Optional[CommitEntry] = None
        self.current_sha: Optional[str] = None
        self.repo_root: Optional[str] = None
        self.pushed: Set[str] = set()
        self.has_remote: bool = False
        self.sync_summary: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ListView(id="commit-list")
            yield ListView(id="file-list")
            yield RichLog(id="diff-view", auto_scroll=False, highlight=False)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Git Log TUI"
        self._load_commits()
        self.query_one("#commit-list", ListView).focus()

    # ---- git 调用封装 -------------------------------------------------
    def _git(self, args: List[str], cwd: Optional[str] = None) -> str:
        try:
            proc = subprocess.run(
                ["git"] + args, cwd=cwd or self.repo_root,
                capture_output=True, encoding="utf-8", errors="replace",
            )
            if proc.returncode != 0:
                return ""
            return proc.stdout.strip()
        except Exception:
            return ""

    def _detect_upstream(self, repo: str, branch: str) -> Tuple[Optional[str], bool]:
        for ref in ("@{upstream}", "origin/%s" % branch):
            out = self._git(["rev-parse", "--abbrev-ref", ref], repo)
            if out:
                return out, True
        return None, False

    # ---- 加载提交列表 -------------------------------------------------
    def _load_commits(self) -> None:
        diff_view = self.query_one("#diff-view", RichLog)
        repo = find_repo_root()
        if repo is None:
            diff_view.clear()
            diff_view.write(Text("当前目录不是 git 仓库", style="red"))
            return
        self.repo_root = repo

        branch = self._git(["rev-parse", "--abbrev-ref", "HEAD"], repo) or "HEAD"
        target = self.ref or "HEAD"

        upstream, has_remote = self._detect_upstream(repo, branch)
        self.has_remote = has_remote
        self.pushed = set()
        if has_remote and upstream is not None:
            ab = self._git(
                ["rev-list", "--left-right", "--count", "%s...%s" % (upstream, target)],
                repo,
            )
            ahead = 0
            behind = 0
            if ab:
                parts = ab.split()
                if len(parts) == 2:
                    behind = int(parts[0] or 0)
                    ahead = int(parts[1] or 0)
            revs = self._git(["rev-list", upstream], repo)
            self.pushed = {line.strip() for line in revs.splitlines() if line.strip()}
            if ahead == 0 and behind == 0:
                self.sync_summary = "%s · 已与 %s 同步" % (branch, upstream)
            else:
                self.sync_summary = "%s · ↑%d ↓%d (相对 %s)" % (branch, ahead, behind, upstream)
        else:
            self.sync_summary = "%s · 无远端跟踪分支" % branch

        # 取日志: 用 \x1f 分隔字段, \x1e 分隔记录, 便于解析
        # 时间格式: absolute -> %ad + 固定格式; relative -> %ar
        if self.date_format == "relative":
            date_field = "%ar"
            date_args: List[str] = []
        else:
            date_field = "%ad"
            date_args = ["--date=format:%Y-%m-%d %H:%M"]
        out = self._git([
            "log", target, "--max-count=300",
        ] + date_args + [
            "--pretty=format:%H%x1f%h%x1f%an%x1f" + date_field + "%x1f%s%x1e",
        ], repo)
        commits: List[CommitEntry] = []
        if out:
            for rec in out.split("\x1e"):
                if not rec.strip():
                    continue
                # 每个字段按 \x1f 切分后需 strip: git 在 format: 各条目之间会插入换行
                f = [part.strip() for part in rec.split("\x1f")]
                if len(f) < 5:
                    continue
                sha, short, author, date, subject = f[0], f[1], f[2], f[3], f[4]
                synced = sha in self.pushed if has_remote else False
                commits.append(CommitEntry(
                    sha=sha, short=short, author=author, date=date,
                    subject=subject, synced=synced, sync_known=has_remote,
                ))
        self.commits = commits

        commit_list = self.query_one("#commit-list", ListView)
        commit_list.clear()
        for c in commits:
            commit_list.append(self._make_commit_item(c))
        self.sub_title = self.sync_summary

        if commits:
            self._select_commit(0)
        else:
            self.query_one("#file-list", ListView).clear()
            diff_view.clear()
            diff_view.write(Text("没有提交记录 (No commits)", style="yellow"))

    # ---- 渲染: 提交项 --------------------------------------------------
    def _sync_marker(self, c: CommitEntry) -> Tuple[str, str]:
        if not c.sync_known:
            return "? ", "dim"
        if c.synced:
            return "✓ ", "green"
        return "↑ ", "yellow"

    def _make_commit_item(self, c: CommitEntry) -> ListItem:
        """提交列表项: 上行 = 同步标记 + 短哈希 + 主题; 下行 = 灰色提交用户与时间。"""
        marker, style = self._sync_marker(c)
        top = Text()
        top.append(marker, style=style)
        top.append(c.short + " ", style="bold")
        subject = c.subject
        if len(subject) > 34:
            subject = subject[:31] + "..."
        top.append(subject)
        bottom = Text()
        bottom.append("%s · %s" % (c.author, c.date), style="dim")
        return ListItem(Label(top), Label(bottom))

    # ---- 选中提交 -> 加载文件列表 ------------------------------------
    def _select_commit(self, idx: Optional[int]) -> None:
        if idx is None or idx < 0 or idx >= len(self.commits):
            return
        c = self.commits[idx]
        self.current_commit = c
        self.current_sha = c.sha
        self._load_files(c.sha)

    def _file_item_text(self, f: FileEntry) -> Text:
        label = Text()
        label.append("[%s] " % status_letter(f.status), style=status_style(f.status))
        label.append(f.path)
        if f.old_path:
            label.append("  (<- %s)" % f.old_path, style="dim")
        return label

    def _load_files(self, sha: str) -> None:
        assert self.repo_root is not None
        file_list = self.query_one("#file-list", ListView)
        out = self._git(
            ["diff-tree", "--no-commit-id", "-r", "--name-status", sha],
            self.repo_root,
        )
        self.files = parse_name_status(out)
        file_list.clear()
        for f in self.files:
            file_list.append(ListItem(Label(self._file_item_text(f))))
        if self.files:
            # 设置索引会触发 highlighted 事件并刷新 diff, 这里再显式刷一次确保即时显示
            file_list.index = 0
            self._show_file_diff(0)
        else:
            diff_view = self.query_one("#diff-view", RichLog)
            diff_view.clear()
            diff_view.write(Text("该提交没有文件改动 (合并提交或空提交)", style="yellow"))

    # ---- 选中文件 -> 显示 diff ---------------------------------------
    def _show_file_diff(self, idx: Optional[int]) -> None:
        diff_view = self.query_one("#diff-view", RichLog)
        diff_view.clear()
        if self.current_sha is None:
            return
        if idx is None or idx < 0 or idx >= len(self.files):
            return
        f = self.files[idx]
        out = self._git(["show", self.current_sha, "--", f.path], self.repo_root)
        out = strip_show_header(out)
        if self.current_commit is not None:
            diff_view.write(Text.from_markup(
                "[b]%s[/b]  [dim]%s · %s · %s[/dim]\n"
                % (self.current_commit.subject, self.current_commit.short,
                   self.current_commit.author, self.current_commit.date)))
        diff_view.write(Text.from_markup(
            "[b]%s[/b]  [dim]%s[/dim]\n" % (f.path, f.status)))
        diff_view.write(render_diff(out))
        diff_view.scroll_home()

    # ---- 事件 ---------------------------------------------------------
    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        idx = event.list_view.index
        if idx is None:
            return
        if event.list_view.id == "commit-list":
            self._select_commit(idx)
        elif event.list_view.id == "file-list":
            self._show_file_diff(idx)

    def action_refresh(self) -> None:
        self._load_commits()


# ============================================================
# 入口
# ============================================================

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="duck-git-log-tui",
        description="基于 Textual 的 git 提交历史查看器 (提交 / 文件 / diff 三栏)",
    )
    parser.add_argument("ref", nargs="?", default=None,
                        help="查看指定分支或引用的提交历史 (默认当前分支 HEAD)")
    parser.add_argument("--date-format", dest="date_format", default="absolute",
                        choices=["absolute", "relative"],
                        help="时间显示格式: absolute 绝对时间(默认) / relative 相对时间")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    GitLogTUI(args.ref, args.date_format).run()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip() if __doc__ else "Usage: duck-git-log-tui [REF]")
        sys.exit(0)
    main()
