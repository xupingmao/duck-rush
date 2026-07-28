# -*- coding: utf-8 -*-
"""
duck-cli —— 传统的交互式 shell（单行提示符，非 TUI）。

特性：
- 维持当前工作目录（cwd），`cd` / 相对路径 / 绝对路径均可
- 基于 prompt_toolkit 的传统行编辑：Tab 触发命令 + 文件补全；↑/↓ 切换历史；Ctrl+C 不退出
- `cd` 不带参数时，调用 duck-chdir 选择器（TUI），等待其结束并切换到它返回的目录；
  `cd <路径>` 与普通 cd 行为相同
- `cd` 选择文件时，调用 duck-file 检查类型；文本文件再用 duck-cat 预览
- 其余命令直接交给系统 shell 执行（继承终端，vim/less 等交互程序照常工作）

用法:
  duck-cli [--path PATH] [-h]

说明:
  duck-cli 只负责「传统 shell 交互」与「调用外部命令」；目录/文件选择交给 duck-chdir，
  类型检查交给 duck-file，文件预览交给 duck-cat。
"""
import os
import re
import sys
import argparse
import logging
import subprocess
import tempfile
from typing import Callable, Iterable, List, Optional

from prompt_toolkit import PromptSession, ANSI
from prompt_toolkit.completion import Completer, Completion, CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory

from duck_utils.os_util import is_windows
from duck_utils.jsonl_util import JsonlStore

# 由本文件位置推导 duck-chdir / duck-file / duck-cat 脚本路径
# （外部命令的调用统一放在 duck-cli 内，duck-chdir 只负责选择并返回结果）
_HERE = os.path.dirname(os.path.abspath(__file__))
DUCK_CHDIR_PATH = os.path.normpath(os.path.join(_HERE, "duck-chdir.py"))
DUCK_FILE_PATH = os.path.normpath(os.path.join(_HERE, "..", "fs", "duck-file.py"))
DUCK_CAT_PATH = os.path.normpath(os.path.join(_HERE, "..", "text", "duck-cat.py"))
DUCK_CALC_PATH = os.path.normpath(os.path.join(_HERE, "..", "math-tools", "duck-calc.py"))

# 内置命令（可被 Tab 补全的首个 token）
BUILTIN_COMMANDS = ["cd", "pwd", "clear", "cls", "exit", "quit"]


def _quote(path: str) -> str:
    """给文件路径加引号，使其在 shell 下正确解析（含空格的路径）。"""
    safe = path.replace('"', '\\"')
    return '"%s"' % safe


def _apply_windows_utf8() -> None:
    """Windows 控制台统一为 UTF-8，避免中文文件名/输出乱码。

    - 将控制台输入/输出代码页切到 65001（UTF-8）
    - 将 Python 自身的 stdout/stderr 重新配置为 UTF-8
    配合 self.env 中的 LC_ALL=C.UTF-8，子进程（如 ls）即可直接输出未转义的
    UTF-8 中文，由 UTF-8 控制台正确渲染，而不是变成 $'\\xxx' 这样的转义方块。
    """
    if not is_windows():
        return
    # 切换控制台代码页到 UTF-8
    try:
        import ctypes
        windll = getattr(ctypes, "windll", None)
        kernel32 = getattr(windll, "kernel32", None) if windll is not None else None
        if kernel32 is not None:
            set_out = getattr(kernel32, "SetConsoleOutputCP", None)
            if callable(set_out):
                set_out(65001)
            set_in = getattr(kernel32, "SetConsoleCP", None)
            if callable(set_in):
                set_in(65001)
    except Exception:  # noqa: ctypes 不可用或调用失败则退回 chcp
        try:
            os.system("chcp 65001 >nul")
        except Exception:
            pass
    # Python 自身以 UTF-8 写终端
    reconfigure_out = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure_out):
        reconfigure_out(encoding="utf-8")
    reconfigure_err = getattr(sys.stderr, "reconfigure", None)
    if callable(reconfigure_err):
        reconfigure_err(encoding="utf-8")


class DuckCompleter(Completer):
    """命令 + 路径补全（prompt_toolkit 版）。

    - 首个 token（命令名）：内置命令 + 历史命令首 token
    - 任意位置含路径片段的词：在当前工作目录下做文件名 / 目录名补全
    """

    def __init__(
        self,
        commands: List[str],
        history_provider: Callable[[], List[str]],
        cwd_provider: Callable[[], str],
    ) -> None:
        super().__init__()
        self._commands = sorted(set(commands))
        self._history_provider = history_provider
        self._cwd_provider = cwd_provider

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        text = document.text_before_cursor
        if not text or text.endswith(" "):
            return
        last_space = text.rfind(" ")
        prefix_before = text[:last_space + 1] if last_space >= 0 else ""
        word = text[last_space + 1:]

        # 首个 token：优先命令名补全（若有候选则只给命令，避免路径噪音）
        if last_space < 0:
            cmds = self._cmd_candidates(word)
            if cmds:
                for c in cmds:
                    yield Completion(c, start_position=-len(word))
                return

        # 文件名 / 目录名补全
        for cand in self._path_candidates(word):
            yield Completion(cand, start_position=-len(word))

    def _cmd_candidates(self, word: str) -> List[str]:
        cands: List[str] = list(self._commands)
        for hist in self._history_provider():
            tok = hist.strip().split(" ", 1)[0]
            if tok:
                cands.append(tok)
        seen = set()
        out: List[str] = []
        for c in cands:
            cf = c.lower()
            if cf.startswith(word.lower()) and cf not in seen:
                seen.add(cf)
                out.append(c)
        return out

    def _path_candidates(self, word: str) -> List[str]:
        """对路径片段做文件名 / 目录名补全，返回补全后的「完整词」列表。"""
        if "\\" in word:
            sep = "\\"
        elif "/" in word:
            sep = "/"
        else:
            sep = None
        if sep is not None:
            dir_part, _, prefix = word.rpartition(sep)
        else:
            dir_part, prefix = "", word

        if word.startswith("~"):
            base = os.path.expanduser("~")
            rel = dir_part[1:] if dir_part.startswith("~") else dir_part
            rel = rel.strip("/\\")
            directory = os.path.join(base, rel) if rel else base
        elif sep is not None and (os.path.isabs(dir_part) or re.match(r"^[A-Za-z]:$", dir_part)):
            directory = dir_part
        else:
            directory = os.path.join(self._cwd_provider(), dir_part) if dir_part else self._cwd_provider()
        if not os.path.isdir(directory):
            return []
        try:
            entries = os.listdir(directory)
        except OSError:
            return []
        entries = [e for e in entries if e not in (".", "..")]
        if not prefix.startswith("."):
            entries = [e for e in entries if not e.startswith(".")]
        matches = [e for e in entries if e.lower().startswith(prefix.lower())]
        out: List[str] = []
        for name in matches:
            full = os.path.join(directory, name)
            if os.path.isdir(full):
                completed = (dir_part + sep if dir_part else "") + name + (sep or os.sep)
            else:
                completed = (dir_part + sep if dir_part else "") + name
            out.append(completed)
        return out


class DuckCli:
    """传统交互式 shell（单行提示符）。"""

    def __init__(self, start_path: str = ".") -> None:
        self.cwd: str = os.path.abspath(start_path)
        self.env: dict = dict(os.environ)
        # Windows 下让 MSYS / GNU 工具以 UTF-8 输出（避免中文文件名被转义成 $'\xxx'）
        if is_windows():
            self.env["LC_ALL"] = "C.UTF-8"
        self.history: List[str] = []
        self._exit_requested: bool = False

        data_dir = os.path.join(os.path.dirname(_HERE), "data", "duck-cli")
        os.makedirs(data_dir, exist_ok=True)
        self._history_path: str = os.path.join(data_dir, "history")
        # 历史持久化（prompt_toolkit 的 FileHistory 格式）
        self._file_history = FileHistory(self._history_path)
        # 同时维护内存历史，供补全器使用
        try:
            with open(self._history_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.rstrip("\n")
                    if line:
                        self.history.append(line)
        except OSError:
            pass
        self._js_store = JsonlStore(os.path.join(data_dir, "history.jsonl"))

        self.completer = DuckCompleter(
            BUILTIN_COMMANDS, lambda: self.history, lambda: self.cwd
        )
        self._session: Optional[PromptSession] = None

    # ------------------------------------------------------------------ #
    # 主循环
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        self._session = PromptSession(
            completer=self.completer,
            history=self._file_history,
        )
        print("duck-cli 已启动（传统 shell 模式）。输入 exit 退出；cd 无参打开目录选择器；Tab 补全；↑↓ 历史；Ctrl+C 不退出。")
        while not self._exit_requested:
            try:
                line = self._session.prompt(self._prompt())
            except KeyboardInterrupt:
                # Ctrl+C：不退出，仅换行重新提示
                sys.stdout.write("\n")
                sys.stdout.flush()
                continue
            except EOFError:
                # Ctrl+D：退出
                break
            self._handle(line)

    def _prompt(self) -> ANSI:
        # DuckCLI 青色加粗，路径绿色；使用 ANSI 上色，路径含特殊字符也安全
        return ANSI(
            "\033[36;1mDuckCLI\033[0m \033[32m%s\033[0m\033[36;1m>\033[0m " % self.cwd
        )

    # ------------------------------------------------------------------ #
    # 命令分发
    # ------------------------------------------------------------------ #
    def _handle(self, raw: str) -> None:
        cmd = raw.strip()
        if not cmd:
            return
        self._remember(cmd)

        low = cmd.lower()
        if low in ("exit", "quit"):
            self._exit_requested = True
            return
        if low in ("clear", "cls"):
            os.system("cls" if is_windows() else "clear")
            return
        if low == "pwd":
            print(self.cwd)
            return
        if cmd == "cd":
            self._run_chdir()
            return
        if cmd.startswith("cd ") or cmd.startswith("cd\t"):
            self._change_dir(cmd[2:].strip())
            return
        # =公式：调用 duck-calc 计算（如 =3*4）
        if cmd.startswith("=") and len(cmd) > 1:
            self._run_calc(cmd[1:].strip())
            return
        # 其余命令交给系统 shell（继承终端，交互程序照常）
        self._run_cmd(cmd)

    def _remember(self, cmd: str) -> None:
        if self.history and self.history[-1] == cmd:
            return
        self.history.append(cmd)
        try:
            self._js_store.write_all(
                [{"cmd": c} for c in self.history], max_records=500, atomic=True
            )
        except OSError:
            pass

    def _change_dir(self, target: str) -> None:
        if not target:
            new = os.path.expanduser("~")
        elif os.path.isabs(target):
            new = target
        else:
            new = os.path.abspath(os.path.join(self.cwd, target))
        if not os.path.isdir(new):
            sys.stderr.write("cd: 不是有效目录: %s\n" % new)
            return
        self.cwd = new

    # ------------------------------------------------------------------ #
    # =公式 -> duck-calc 计算
    # ------------------------------------------------------------------ #
    def _run_calc(self, formula: str) -> None:
        try:
            subprocess.run(
                [sys.executable, DUCK_CALC_PATH, formula],
                cwd=self.cwd, env=self.env,
            )
        except Exception as e:  # noqa: 任意异常都不应让 shell 崩溃
            sys.stderr.write("计算失败: %s\n" % e)

    # ------------------------------------------------------------------ #
    # 执行外部命令（继承终端，Ctrl+C 只作用于子进程，不影响 shell）
    # ------------------------------------------------------------------ #
    def _run_cmd(self, cmd: str) -> None:
        try:
            subprocess.run(
                cmd,
                shell=True,
                cwd=self.cwd,
                env=self.env,
                start_new_session=(not is_windows()),
                creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if is_windows() else 0),
            )
        except KeyboardInterrupt:
            # 理论上子进程在独立进程组，Ctrl+C 不会到达这里；兜底处理
            sys.stdout.write("^C\n")
        except Exception as e:  # noqa: 任意异常都不应让 shell 崩溃
            sys.stderr.write("执行失败: %s\n" % e)

    # ------------------------------------------------------------------ #
    # cd 无参 -> duck-chdir 选择器
    # ------------------------------------------------------------------ #
    def _run_chdir(self) -> None:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tf:
                result_file = tf.name
            try:
                os.remove(result_file)
            except OSError:
                pass
            # 交接终端给 duck-chdir（Textual TUI），结束后自动恢复
            subprocess.run(
                [sys.executable, DUCK_CHDIR_PATH, self.cwd, "--result-file", result_file],
                cwd=self.cwd, env=self.env,
            )
            line = ""
            try:
                with open(result_file, "r", encoding="utf-8") as f:
                    line = f.read().strip()
            except OSError:
                line = ""
            try:
                os.remove(result_file)
            except OSError:
                pass
        except Exception as e:  # noqa
            sys.stderr.write("目录切换失败: %s\n" % e)
            return

        if not line or line == "exit":
            sys.stderr.write("已取消目录切换\n")
        elif line.startswith("dir "):
            target = line[4:].strip()
            self._change_dir(target)
            sys.stderr.write("已切换到: %s\n" % target)
        elif line.startswith("file "):
            target = line[5:].strip()
            self._preview_if_text(target)
        else:
            sys.stderr.write("未知结果: %s\n" % line)

    def _preview_if_text(self, path: str) -> None:
        """file 结果：调用 duck-file 检查类型（-i MIME, -b 仅类型）。
        若是文本文件，交接终端给 duck-cat 预览（--highlight 上色，限制 1000 行）。
        """
        try:
            result = subprocess.run(
                [sys.executable, DUCK_FILE_PATH, "-i", "-b", path],
                capture_output=True, text=True, cwd=self.cwd,
            )
        except Exception as e:  # noqa
            sys.stderr.write("类型检测失败: %s\n" % e)
            return
        if result.returncode != 0:
            sys.stderr.write("类型检测失败: %s\n" % (result.stderr.strip() or "unknown"))
            return
        mime = result.stdout.strip()
        is_text = mime.startswith("text/") or mime == "application/x-empty"
        if not is_text:
            sys.stderr.write("二进制文件，不预览: %s (%s)\n" % (path, mime))
            return
        # 文本：交接终端给 duck-cat 预览
        try:
            subprocess.run(
                [sys.executable, DUCK_CAT_PATH, "--max-lines", "1000",
                 "--highlight", path],
                cwd=self.cwd, env=self.env,
            )
        except Exception as e:  # noqa
            sys.stderr.write("预览失败: %s\n" % e)


def main() -> None:
    # -h/--help 必须无副作用（不得改变控制台、不写文件），放最开头直接退出
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    # 抑制 asyncio 的 debug 噪声（如 "Using proactor: IocpProactor"）
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    _apply_windows_utf8()
    parser = argparse.ArgumentParser(
        description="传统的交互式 shell（单行提示符，非 TUI）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--path", default=".", help="初始工作目录（默认当前目录）")
    args = parser.parse_args()

    start = args.path if os.path.isdir(args.path) else os.getcwd()
    DuckCli(start_path=start).run()


if __name__ == "__main__":
    main()
