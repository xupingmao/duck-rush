# -*- coding: utf-8 -*-
"""
duck-fav —— 文件收藏夹 CLI（JSONL 存储）。

子命令:
  add <路径> [路径...]   收藏一个或多个文件 / 目录（按规范化绝对路径去重）
  rm  <路径> [路径...]    取消收藏（按规范化绝对路径匹配）
  rm  --id <id> [id...]  按记录 id 取消收藏（id 见 list 输出）
  list                   列出全部收藏（每行 "#id<TAB>路径"，按路径名称排序）
  clear                  清空收藏（-y 跳过确认）
  select                 进入 TUI 选择收藏项（参考 duck-chdir 协议）

无参数直接运行 `duck-fav` 等价于 `duck-fav select`，进入交互式选择模式
（结果通过 stdout 或 --result-file 输出，供 duck-cli 等调用方解析并切换目录）。

select 结果协议（供调用方 duck-cli 解析，与 duck-chdir 一致）:
    dir  <绝对路径>    选择了一个目录
    file <绝对路径>    选择了一个文件
    exit               直接退出（未选择）
  作为独立命令运行时，结果打印到 stdout；
  通过 --result-file 调用时（如 duck-cli 内 `duck-fav select`），结果写入该文件，
  由 duck-cli 据此切换当前目录或预览文件。

存储位置: get_command_data_dir("duck-fav")/bookmarks.jsonl，
每行一个 JSON 对象 {"id": 整数, "path": "绝对路径"}（id 为唯一整型编号，
旧记录（无 id）在首次 list/add/rm 时自动补齐）。

用法:
  duck-fav add ./notes.txt
  duck-fav list
  duck-fav rm ./notes.txt
  duck-fav rm --id 3
  duck-fav clear -y
  duck-fav select

说明:
  -h/--help 必须无副作用（不读写文件、不启动 TUI），放 main 最开头直接退出。
"""
import argparse
import os
import sys
from dataclasses import dataclass
from typing import List, Optional

from prompt_toolkit import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style

from duck_utils.jsonl_util import JsonlStore
from duck_utils.os_util import get_command_data_dir


def _store() -> JsonlStore:
    """返回收藏夹的 JsonlStore（文件不存在时由 JsonlStore 自动创建）。"""
    path = os.path.join(get_command_data_dir("duck-fav"), "bookmarks.jsonl")
    return JsonlStore(path)


def _key(path: str) -> str:
    """去重 / 匹配键：展开 ~、规范化并统一大小写。

    Windows 文件系统大小写不敏感，统一 normcase 后 C:\\a 与 c:\\a 视为同一文件，
    避免同一文件因大小写差异被重复收藏。
    """
    return os.path.normcase(os.path.abspath(os.path.expanduser(path)))


def _display(path: str) -> str:
    """存储用的展示路径：保留原始大小写（更贴近资源管理器 / ls 显示）。"""
    return os.path.abspath(os.path.expanduser(path))


def _all_paths(store: JsonlStore) -> List[str]:
    # 默认按路径名称排序 (大小写不敏感), 让 list / select 展示顺序稳定一致
    return sorted(
        (rec["path"] for rec in store.read_all() if rec.get("path")),
        key=lambda p: os.path.normcase(p),
    )


def _read_records(store: JsonlStore) -> List[dict]:
    """读取全部收藏记录, 并为缺少 id 的旧记录补齐顺序 id（原地写回）。

    返回的每个 dict 都包含 "id"(int) 与 "path" 字段, 供 list / rm --id 使用。
    """
    recs = store.read_all()
    if any("id" not in r for r in recs):
        used: set = set()
        nxt = 1
        for r in recs:
            rid = r.get("id")
            if isinstance(rid, int):
                used.add(rid)
        for r in recs:
            if "id" not in r:
                while nxt in used:
                    nxt += 1
                r["id"] = nxt
                used.add(nxt)
        store.write_all(recs, atomic=True)
    return recs


def _next_id(recs: List[dict]) -> int:
    """在已有记录基础上, 返回下一个未被占用的整型 id。"""
    used = set(r.get("id") for r in recs if isinstance(r.get("id"), int))
    nxt = 1
    while nxt in used:
        nxt += 1
    return nxt


def cmd_add(store: JsonlStore, paths: List[str]) -> int:
    recs = _read_records(store)
    existing = set(_key(r.get("path", "")) for r in recs)
    nxt = _next_id(recs)
    added = 0
    for p in paths:
        key = _key(p)
        if key in existing:
            continue
        disp = _display(p)
        store.append({"id": nxt, "path": disp})
        existing.add(key)
        print("已收藏 [#%d]: %s" % (nxt, disp))
        nxt += 1
        added += 1
    if added == 0:
        print("无新增（全部已存在）")
    return 0


def cmd_rm(store: JsonlStore, paths: List[str], ids: Optional[List[int]] = None) -> int:
    recs = _read_records(store)
    if ids:
        idset = set(ids)
        kept = [r for r in recs if r.get("id") not in idset]
    else:
        targets = set(_key(p) for p in paths)
        kept = [r for r in recs if _key(r.get("path", "")) not in targets]
    removed = len(recs) - len(kept)
    if removed == 0:
        print("未找到匹配项")
        return 0
    store.write_all(kept, atomic=True)
    print("已取消收藏 %d 项" % removed)
    return 0


def cmd_list(store: JsonlStore) -> int:
    recs = _read_records(store)
    if not recs:
        print("（空）")
        return 0
    for r in sorted(recs, key=lambda r: os.path.normcase(r.get("path", ""))):
        print("#%s\t%s" % (r.get("id"), r.get("path")))
    return 0


def cmd_clear(store: JsonlStore, yes: bool) -> int:
    if not yes:
        ans = input("确认清空全部收藏? [y/N] ").strip().lower()
        if ans != "y":
            print("已取消")
            return 0
    store.write_all([], atomic=True)
    print("已清空收藏")
    return 0


# ------------------------------------------------------------------ #
# select —— 基于 prompt_toolkit 的收藏项选择器（纯选择，不调用外部命令）
# ------------------------------------------------------------------ #
@dataclass
class FavEntry:
    """列表中的一项：path 为绝对路径，kind 区分目录 / 文件，missing 标记是否已不存在。"""

    path: str
    kind: str          # "dir" | "file"
    missing: bool


_STYLE_FAV = Style.from_dict(
    {
        "title": "ansigreen bold",
        "dir": "ansicyan",
        "file": "ansiwhite",
        "missing": "ansired",
        "selected": "reverse",
        "toolbar": "ansigray",
    }
)


class FavSelectApp:
    """基于 prompt_toolkit 的收藏项选择器（参考 duck-chdir 的纯选择器设计）。"""

    def __init__(self, paths: List[str], result_file: Optional[str] = None) -> None:
        self.result_file: Optional[str] = result_file
        self.entries: List[FavEntry] = []
        self.index: int = 0
        self.result: Optional[str] = None
        self._pt_app: Optional[Application] = None
        self._build_entries(paths)
        self._pt_app = self._build()

    def _build_entries(self, paths: List[str]) -> None:
        entries: List[FavEntry] = []
        for p in paths:
            kind = "dir" if os.path.isdir(p) else "file"
            entries.append(FavEntry(p, kind, missing=not os.path.exists(p)))
        self.entries = entries

    def _get_text(self) -> FormattedText:
        ft = FormattedText()
        ft.append(
            ("class:title", "duck-fav 收藏夹 — 选择一项"
             "（↑/↓ 移动，Enter 确认，q/Esc 取消）\n\n")
        )
        # 视口：内容超过一屏时围绕当前选中项居中显示
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
            cls = "missing" if e.missing else e.kind
            style = ("class:selected," if i == self.index else "class:") + cls
            marker = "> " if i == self.index else "  "
            icon = "[目录] " if e.kind == "dir" else "[文件] "
            label = e.path + ("  (不存在)" if e.missing else "")
            ft.append((style, marker + icon + label))
            ft.append(("", "\n"))
        if n > avail:
            ft.append(("class:toolbar", "... 更多项，用 ↑/↓ 浏览 ...\n"))
        return ft

    def _emit(self, line: str) -> None:
        """记录选择结果并退出 prompt_toolkit 应用。"""
        self.result = line
        if self._pt_app is not None:
            self._pt_app.exit()

    def _act(self, entry: FavEntry) -> None:
        if entry.kind == "dir":
            self._emit("dir %s" % entry.path)
        else:
            self._emit("file %s" % entry.path)

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

        @bindings.add("q")
        @bindings.add("escape")
        def _quit(event: object) -> None:  # noqa: 退出（未选择）
            self._emit("exit")

        @bindings.add("c-c")
        def _ctrl_c(event: object) -> None:  # noqa: Ctrl+C 不崩溃，等同退出
            self._emit("exit")

        control = FormattedTextControl(self._get_text, focusable=True)
        layout = Layout(Window(control))
        return Application(
            layout=layout,
            key_bindings=bindings,
            style=_STYLE_FAV,
            full_screen=True,
            mouse_support=False,
        )

    def run(self) -> None:
        assert self._pt_app is not None
        self._pt_app.run()


def _write_result(line: str, result_file: Optional[str]) -> None:
    """把选择结果输出（写文件或打印 stdout），与 duck-chdir 协议一致。"""
    if result_file:
        try:
            with open(result_file, "w", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            sys.stderr.write("写入结果失败: %s\n" % e)
    else:
        print(line)


def cmd_select(store: JsonlStore, result_file: Optional[str] = None) -> int:
    paths = _all_paths(store)
    if not paths:
        sys.stderr.write("收藏夹为空，没有可选项\n")
        _write_result("exit", result_file)
        return 0
    try:
        app = FavSelectApp(paths, result_file=result_file)
        app.run()
    except Exception as e:  # noqa: 异常（如无终端）通过退出码 + stderr 暴露给调用方
        sys.stderr.write("duck-fav select 异常: %s\n" % e)
        return 1
    line = app.result if app.result is not None else "exit"
    _write_result(line, result_file)
    return 0


def main() -> None:
    # -h/--help 必须无副作用，放最开头直接退出
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="文件收藏夹 CLI（JSONL 存储）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="收藏文件/目录")
    p_add.add_argument("paths", nargs="+", help="一个或多个路径")

    p_rm = sub.add_parser("rm", help="取消收藏（按路径或 --id）")
    p_rm.add_argument("paths", nargs="*", help="一个或多个路径（按规范化绝对路径匹配）")
    p_rm.add_argument("--id", nargs="+", type=int, default=None,
                      help="按记录 id 删除（与 paths 二选一）")

    sub.add_parser("list", help="列出收藏")

    p_clear = sub.add_parser("clear", help="清空收藏")
    p_clear.add_argument("-y", "--yes", action="store_true", help="跳过确认")

    p_select = sub.add_parser("select", help="进入 TUI 选择收藏项")
    p_select.add_argument("--result-file", default=None,
                          help="将选择结果写入该文件（供调用方读取）；不传则打印到 stdout")

    args = parser.parse_args()
    store = _store()
    if not args.command:
        # 无参数直接运行等价于 `duck-fav select`：进入交互式选择（供 duck-cli 直接调用）
        sys.exit(cmd_select(store))

    if args.command == "add":
        sys.exit(cmd_add(store, args.paths))
    elif args.command == "rm":
        if not args.paths and not args.id:
            sys.stderr.write("duck-fav rm: 请指定路径或 --id\n")
            sys.exit(2)
        sys.exit(cmd_rm(store, args.paths, args.id))
    elif args.command == "list":
        sys.exit(cmd_list(store))
    elif args.command == "clear":
        sys.exit(cmd_clear(store, args.yes))
    elif args.command == "select":
        sys.exit(cmd_select(store, args.result_file))


if __name__ == "__main__":
    main()
