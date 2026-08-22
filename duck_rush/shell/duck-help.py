# -*- coding: utf-8 -*-
"""
duck-help —— 交互式帮助浏览器 (prompt_toolkit 实现的纯 TUI)。

列出全部 duck-* 工具, 通过方向键 (或 j/k) 浏览, 输入字符可实时筛选,
Enter 启动选中的工具 (启动后返回仍在浏览器内), → 查看该工具的完整 -h 帮助,
q / Esc 退出。

特性:
- ↑/↓ 或 j/k 选择 (筛选模式下仅方向键导航, 字母用于输入筛选词)
- 输入任意字母/数字/.-_ 进入筛选 (也会自动进入筛选模式), Esc 清除筛选
- / 主动进入/重设筛选; Backspace 删除筛选字符
- Enter 启动选中的工具, 结束后返回浏览器
- → 或 l 查看选中工具的完整 -h 帮助, ← 或 h 返回简介
- q / Esc (无筛选时) / Ctrl+C 退出

用法:
  duck-help [--result-file FILE] [-h]

说明:
  -h/--help 必须无副作用 (不启动 TUI、不写文件), 放 main 最开头直接退出。
  作为 duck-cli 的 `help`/`h` 内置命令, 以及 `duck help` / `duck h` 顶层指令的
  实现, 被调用方交接终端后运行, 退出后控制交还调用方。
  对 duck-chdir / duck-fav 这类「导航选择器」, 浏览器以 --result-file 协议启动它们,
  选择目录/文件后把结果 (dir <路径> / file <路径>) 透传给调用方 (duck-cli 据此切换目录)。
"""
import argparse
import os
import sys
import subprocess
import tempfile
from typing import List, Optional, Tuple

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window, HSplit, VSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style

from duck_utils.duck_meta import InstallMeta


# 命令发现的扫描参数 (与 duck.py 的 get_command_list 保持一致)
_COMMAND_EXT_SET = {".py", ".sh"}
_SKIP_DIRS = {"web-tools", "gui-tools", "lib", "data", "local", "__pycache__"}
# 本工具自身不作为可启动项出现, 避免从浏览器里再启动自己
_SELF_NAME = "duck-help"
# 置顶展示的常用工具 (在列表中排在其它命令之前)
_PINNED_COMMANDS = ["duck-chdir", "duck-fav"]
# 导航选择器类工具: 以 --result-file 协议启动, 并把结果透传给调用方 (duck-cli 切换目录)
_NAV_COMMANDS = {"duck-chdir", "duck-fav"}

_STYLE = Style.from_dict(
    {
        "title": "ansibrightgreen bold",
        "path": "ansibrightblue bold",
        "cmdname": "ansibrightcyan",
        "count": "ansibrightblack",
        "selected": "reverse",
        "desc": "ansibrightblack",
        "toolbar": "ansibrightyellow",
        "help": "ansiwhite",
    }
)


def _trunc(text: str, width: int) -> str:
    """按字符数截断 (中文按 1 字符计, 仅用于列表行内简介, 近似即可)。"""
    if len(text) <= width:
        return text
    return text[: max(1, width - 1)] + "…"


def _command_sort_key(item: Tuple[str, str, str]) -> Tuple[int, str]:
    """排序键: 置顶命令按 _PINNED_COMMANDS 顺序在前, 其余按名称排序。"""
    name = item[0]
    if name in _PINNED_COMMANDS:
        return (_PINNED_COMMANDS.index(name), name)
    return (len(_PINNED_COMMANDS), name)


def _discover_commands() -> List[Tuple[str, str, str]]:
    """发现全部 duck-* 命令, 返回 [(name, fpath, ext), ...] 排序后列表。

    置顶命令 (_PINNED_COMMANDS) 排在最前, 其余按名称排序。
    主源码目录就地跳过非命令目录 (web-tools/gui-tools/lib/data/local),
    并合并 ~/.duck-rush/duck.json 中登记的外部工具源码目录。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    duck_rush_dir = os.path.dirname(here)
    roots: List[str] = [duck_rush_dir]
    try:
        roots.extend(InstallMeta.load().get_external_src_dirs())
    except Exception:
        pass

    cmds: List[Tuple[str, str, str]] = []
    seen: set = set()
    for src_root in roots:
        if not os.path.isdir(src_root):
            continue
        is_main = (src_root == duck_rush_dir)
        for root, dirs, files in os.walk(src_root):
            if is_main:
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for fname in files:
                if fname == "duck.py" or fname.startswith("__") or fname.startswith("test_"):
                    continue
                name, ext = os.path.splitext(fname)
                if ext not in _COMMAND_EXT_SET:
                    continue
                if fname.endswith("_util.py"):
                    continue
                if name == _SELF_NAME or name in seen:
                    continue
                seen.add(name)
                cmds.append((name, os.path.join(root, fname), ext))
    cmds.sort(key=_command_sort_key)
    return cmds


def _load_desc_cache() -> dict:
    """读取安装时生成的命令简介缓存 (data/install/command_desc.jsonl)。"""
    cache: dict = {}
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cache_file = os.path.join(project_root, "data", "install", "command_desc.jsonl")
    if not os.path.exists(cache_file):
        return cache
    try:
        with open(cache_file, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                obj = __import__("json").loads(line)
                cache[obj.get("name", "")] = obj.get("desc", "")
    except Exception:
        return {}
    return cache


def _describe(name: str, fpath: str, ext: str) -> str:
    """运行 {cmd} -h 提取首行非空内容作为简介; 失败返回空串。"""
    if ext == ".py":
        cmdline = [sys.executable, fpath, "-h"]
    elif ext == ".sh":
        cmdline = ["bash", fpath, "-h"]
    else:
        return ""
    try:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["LC_ALL"] = "C.UTF-8"
        env["LANG"] = "C.UTF-8"
        proc = subprocess.run(
            cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=3
        )
        out = proc.stdout.decode("utf-8", errors="replace")
    except Exception:
        return ""
    for line in out.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _help_text(name: str, fpath: str, ext: str) -> str:
    """运行 {cmd} -h 取完整帮助文本; 失败返回提示。"""
    if ext == ".py":
        cmdline = [sys.executable, fpath, "-h"]
    elif ext == ".sh":
        cmdline = ["bash", fpath, "-h"]
    else:
        return "(该类型命令不支持 -h 帮助)"
    try:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["LC_ALL"] = "C.UTF-8"
        env["LANG"] = "C.UTF-8"
        proc = subprocess.run(
            cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=5
        )
        out = proc.stdout.decode("utf-8", errors="replace")
    except Exception as e:  # noqa: 任意异常都不应让浏览器崩溃
        return "(获取帮助失败: %s)" % e
    return out.strip() or "(无帮助输出)"


class HelpApp:
    """基于 prompt_toolkit 的工具浏览器 (启动工具后返回仍在浏览器)。"""

    def __init__(self, commands: List[Tuple[str, str, str]]) -> None:
        self.commands = commands
        self.desc: dict = _load_desc_cache()
        self.help_cache: dict = {}
        self.index: int = 0
        self.query: str = ""
        self.filter_mode: bool = False
        self._filter_prev: str = ""
        self.detail_help: bool = False
        self.result: Optional[str] = None
        # 导航选择器 (duck-chdir/duck-fav) 选中的结果行, 供调用方 (duck-cli) 切换目录
        self.result_line: Optional[str] = None
        self._pt_app: Optional[Application] = None

    # ------------------------------------------------------------------ #
    # 列表 / 筛选 / 导航
    # ------------------------------------------------------------------ #
    def _filtered(self) -> List[Tuple[str, str, str]]:
        if not self.query:
            return self.commands
        q = self.query.lower()
        out: List[Tuple[str, str, str]] = []
        for name, fpath, ext in self.commands:
            d = self.desc.get(name, "") or ""
            if q in name.lower() or q in d.lower():
                out.append((name, fpath, ext))
        return out

    def _clamp_index(self) -> None:
        n = len(self._filtered())
        if n == 0:
            self.index = 0
        elif self.index >= n:
            self.index = n - 1
        elif self.index < 0:
            self.index = 0

    def _move(self, delta: int) -> None:
        filt = self._filtered()
        if not filt:
            return
        self.index = max(0, min(len(filt) - 1, self.index + delta))

    def _append(self, ch: str) -> None:
        if not self.filter_mode:
            # 普通模式下输入字母不触发筛选, 仅方向键/jk 导航
            return
        self.query += ch
        self._clamp_index()

    def _ensure_desc(self, name: str, fpath: str, ext: str) -> None:
        if self.desc.get(name):
            return
        d = _describe(name, fpath, ext)
        if d:
            self.desc[name] = d

    def _fetch_help(self, name: str, fpath: str, ext: str) -> str:
        if name in self.help_cache:
            return self.help_cache[name]
        text = _help_text(name, fpath, ext)
        self.help_cache[name] = text
        return text

    # ------------------------------------------------------------------ #
    # 渲染
    # ------------------------------------------------------------------ #
    def _get_title_text(self) -> FormattedText:
        total = len(self.commands)
        suffix = ""
        if self.filter_mode:
            suffix = "   [筛选中]"
        elif self.query:
            suffix = "   筛选: " + self.query
        return FormattedText(
            [("class:title", "duck-rush 交互式帮助 (共 %d 个命令)%s" % (total, suffix))]
        )

    def _get_toolbar_text(self) -> FormattedText:
        if self.filter_mode:
            hint = "筛选模式: '%s'_   输入过滤, Enter 确认, Esc 取消" % self.query
        elif self.query:
            hint = "筛选: '%s'   / 重设筛选, Esc 清除, q 退出" % self.query
        else:
            hint = "↑/↓ 选择   Enter 启动   → 详情   / 筛选   q 退出"
        return FormattedText([("class:toolbar", hint)])

    def _get_left_text(self) -> FormattedText:
        ft = FormattedText()
        filt = self._filtered()
        n = len(filt)
        if n == 0:
            ft.append(("class:toolbar", "(无匹配命令)\n"))
            ft.append(("class:toolbar", "输入字符筛选, Esc 清除筛选, q 退出\n"))
            return ft

        avail = 1 << 30
        try:
            from prompt_toolkit.application import get_app
            avail = max(1, get_app().output.get_size().rows - 4)
        except Exception:  # noqa: 非运行期退化为全部显示
            pass

        top = 0
        if n > avail:
            top = max(0, min(self.index - avail // 2, n - avail))
        for i in range(top, min(n, top + avail)):
            name, fpath, ext = filt[i]
            sel = (i == self.index)
            style = ("class:selected," if sel else "class:") + "cmdname"
            marker = "> " if sel else "  "
            ft.append((style, marker + name))
            d = self.desc.get(name, "") or ""
            if d:
                ft.append(("class:count", "  " + _trunc(d, 22)))
            ft.append(("", "\n"))
        if n > avail:
            ft.append(("class:toolbar", "... ↑/↓ 浏览 ...\n"))
        return ft

    def _get_right_text(self) -> FormattedText:
        ft = FormattedText()
        filt = self._filtered()
        if not filt:
            ft.append(("class:toolbar", "(无匹配命令)\n"))
            return ft
        name, fpath, ext = filt[self.index]
        if self.detail_help:
            text = self._fetch_help(name, fpath, ext)
            ft.append(("class:path", name + " 帮助:\n\n"))
            ft.append(("class:help", text))
            ft.append(("", "\n\n"))
            ft.append(("class:toolbar", "← 返回简介   q 退出\n"))
        else:
            self._ensure_desc(name, fpath, ext)
            d = self.desc.get(name, "") or "(暂无简介, 按 → 查看完整帮助)"
            ft.append(("class:path", "命令: " + name + "\n\n"))
            ft.append(("class:help", d + "\n\n"))
            ft.append(("class:toolbar", "用法:\n"))
            ft.append(("", "  duck %s [参数]\n" % name))
            ft.append(("", "  duck %s -h   完整帮助\n\n" % name))
            ft.append(("class:toolbar", "Enter 启动该工具\n→ 查看详情   / 筛选   q 退出\n"))
        return ft

    # ------------------------------------------------------------------ #
    # 交互
    # ------------------------------------------------------------------ #
    def _launch(self, fpath: str, ext: str) -> None:
        name = os.path.splitext(os.path.basename(fpath))[0]
        if name in _NAV_COMMANDS:
            # 导航选择器: 以 --result-file 协议启动, 选中后把结果透传给调用方
            self._launch_picker(name, fpath)
            return
        if ext == ".py":
            cmd = [sys.executable, fpath]
        elif ext == ".sh":
            cmd = ["bash", fpath]
        else:
            return
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["LC_ALL"] = "C.UTF-8"
        env["LANG"] = "C.UTF-8"
        try:
            subprocess.run(cmd, env=env)
        except Exception as e:  # noqa: 任意异常都不应让浏览器崩溃
            sys.stdout.write("\n启动失败: %s\n" % e)

    def _launch_picker(self, name: str, fpath: str) -> None:
        """以 --result-file 协议启动导航选择器, 读取 dir/file 结果。

        duck-chdir 直接接受 --result-file; duck-fav 需要显式 `select` 子命令。
        选中的 dir/file 结果写入 self.result_line, 由 run() 返回给调用方。
        """
        tmp = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tf:
                tmp = tf.name
            try:
                os.remove(tmp)
            except OSError:
                pass
            if name == "duck-fav":
                cmd = [sys.executable, fpath, "select", "--result-file", tmp]
            else:
                cmd = [sys.executable, fpath, "--result-file", tmp]
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "utf-8"
            env["LC_ALL"] = "C.UTF-8"
            env["LANG"] = "C.UTF-8"
            subprocess.run(cmd, env=env)
            line = ""
            try:
                with open(tmp, "r", encoding="utf-8") as f:
                    line = f.read().strip()
            except OSError:
                line = ""
            if line.startswith("dir ") or line.startswith("file "):
                self.result_line = line
        except Exception as e:  # noqa: 任意异常都不应让浏览器崩溃
            sys.stdout.write("\n启动失败: %s\n" % e)
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def _build(self) -> Application:
        bindings = KeyBindings()

        @bindings.add("up")
        def _up(event: object) -> None:  # noqa: 参数由 prompt_toolkit 注入
            self._move(-1)

        @bindings.add("down")
        def _down(event: object) -> None:  # noqa
            self._move(1)

        @bindings.add("k")
        def _k(event: object) -> None:  # noqa
            if self.filter_mode:
                self._append("k")
            else:
                self._move(-1)

        @bindings.add("j")
        def _j(event: object) -> None:  # noqa
            if self.filter_mode:
                self._append("j")
            else:
                self._move(1)

        @bindings.add("h")
        def _h(event: object) -> None:  # noqa
            if self.filter_mode:
                self._append("h")
            elif self.detail_help:
                self.detail_help = False
            elif self.query:
                self.query = ""

        @bindings.add("l")
        def _l(event: object) -> None:  # noqa
            if self.filter_mode:
                self._append("l")
            else:
                self.detail_help = not self.detail_help

        @bindings.add("left")
        def _left(event: object) -> None:  # noqa
            if not self.filter_mode:
                if self.detail_help:
                    self.detail_help = False
                elif self.query:
                    self.query = ""

        @bindings.add("right")
        def _right(event: object) -> None:  # noqa
            if not self.filter_mode:
                self.detail_help = not self.detail_help

        @bindings.add("enter")
        def _enter(event: object) -> None:  # noqa
            if self.filter_mode:
                self.filter_mode = False
                return
            filt = self._filtered()
            if filt:
                self.result = filt[self.index][1]
                assert self._pt_app is not None
                self._pt_app.exit()

        @bindings.add("escape")
        def _esc(event: object) -> None:  # noqa
            if self.filter_mode:
                self.query = self._filter_prev
                self.filter_mode = False
                self._clamp_index()
            elif self.query:
                self.query = ""
            else:
                self.result = None
                assert self._pt_app is not None
                self._pt_app.exit()

        @bindings.add("backspace")
        def _bs(event: object) -> None:  # noqa
            if self.filter_mode:
                self.query = self.query[:-1]
                self._clamp_index()

        @bindings.add("/")
        def _slash(event: object) -> None:  # noqa
            if not self.filter_mode:
                self._filter_prev = self.query
                self.query = ""
                self.filter_mode = True

        @bindings.add("q")
        def _q(event: object) -> None:  # noqa
            self.result = None
            assert self._pt_app is not None
            self._pt_app.exit()

        @bindings.add("c-c")
        def _ctrl_c(event: object) -> None:  # noqa
            self.result = None
            assert self._pt_app is not None
            self._pt_app.exit()

        # 其余可输入字符: 筛选模式下追加到查询, 普通模式下忽略
        for _ch in "abcdefgimnoprstuvwxyz0123456789-._":
            @bindings.add(_ch)
            def _type(event: object, ch: str = _ch) -> None:  # noqa
                self._append(ch)

        @bindings.add("space")
        def _space(event: object) -> None:  # noqa
            self._append(" ")

        title = FormattedTextControl(self._get_title_text, focusable=False)
        left = FormattedTextControl(self._get_left_text, focusable=True)
        right = FormattedTextControl(self._get_right_text, focusable=False)
        toolbar = FormattedTextControl(self._get_toolbar_text, focusable=False)
        layout = Layout(
            HSplit(
                [
                    Window(title, height=1),
                    VSplit([Window(left, width=46), Window(right)]),
                    Window(toolbar, height=1),
                ]
            )
        )
        return Application(
            layout=layout,
            key_bindings=bindings,
            style=_STYLE,
            full_screen=True,
            mouse_support=False,
        )

    def run(self) -> Optional[str]:
        """运行浏览器; 返回导航选择器 (duck-chdir/duck-fav) 的结果行, 无则返回 None。"""
        while True:
            self._pt_app = self._build()
            assert self._pt_app is not None
            self._pt_app.run()
            if not self.result:
                break
            fpath = self.result
            ext = os.path.splitext(fpath)[1]
            self.result = None
            self._launch(fpath, ext)
            return self.result_line
        return self.result_line


def main() -> None:
    # -h/--help 必须无副作用 (不启动 TUI、不写文件), 放最开头直接退出
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="交互式帮助浏览器: 列出全部 duck-* 工具并可用方向键浏览/启动",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--result-file", default=None,
                        help="将导航选择器 (duck-chdir/duck-fav) 的结果写入该文件; 不传则不输出")
    args = parser.parse_args()

    commands = _discover_commands()
    if not commands:
        sys.stderr.write("未发现任何 duck-* 命令\n")
        sys.exit(1)
    line = HelpApp(commands).run()
    if args.result_file and line:
        try:
            with open(args.result_file, "w", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            sys.stderr.write("写入结果失败: %s\n" % e)


if __name__ == "__main__":
    main()
