# encoding=utf-8
import sys
import subprocess
import os
import json
import platform
import shutil
import threading
from typing import List, NamedTuple, Optional

def popen(cmd):
    proc = subprocess.Popen(cmd,
                            shell=True,
                            stdout=subprocess.PIPE)
    return proc.stdout

def popen_str(cmd, encoding="utf-8") -> str:
    return popen(cmd).read().decode(encoding=encoding)


def exec_cmd(cmd="", do_print=True):
    if do_print:
        print(cmd)
    os.system(cmd)

def set_console_font_color(color):
    """设置终端的字体颜色"""
    if color == "red":
        sys.stdout.write("\033[31m")
    if color == "green":
        sys.stdout.write("\033[32m")
    if color == "orange":
        sys.stdout.write("\033[33m")
    if color == "blue":
        sys.stdout.write("\033[34m")
    if color == "default":
        sys.stdout.write("\033[0m")


def is_windows():
    return os.name == "nt"

def is_mac():
    return platform.system() == "Darwin"

def is_linux():
    return os.name == "linux"


def get_duck_rush_home() -> str:
    """返回 duck_rush 的用户级根目录 ~/.duck-rush（仅返回路径，不创建）。"""
    return os.path.join(os.path.expanduser("~"), ".duck-rush")


def get_data_dir() -> str:
    """返回命令数据存储根目录 ~/.duck-rush/data（自动创建并返回）。"""
    d = os.path.join(get_duck_rush_home(), "data")
    os.makedirs(d, exist_ok=True)
    return d


def get_command_data_dir(cmd: str) -> str:
    """返回单个命令 {cmd} 的数据目录 ~/.duck-rush/data/{cmd}（自动创建并返回）。

    命令需要持久化运行时数据（缓存、状态文件等）时统一放在这里，
    避免污染仓库或散落各处。
    """
    d = os.path.join(get_data_dir(), cmd)
    os.makedirs(d, exist_ok=True)
    return d


class CmdInfo(NamedTuple):
    """系统命令信息。path 为 None 表示 shell 内建命令 / 函数 / 别名。"""
    name: str
    path: Optional[str]


def list_commands(pattern: Optional[str] = None,
                  refresh: bool = False) -> List[CmdInfo]:
    """调用 duck-list-cmd 命令获取系统命令列表。

    Args:
        pattern: 按名称子串过滤（不区分大小写），None 表示不过滤。
        refresh: True 时忽略 duck-list-cmd 的缓存，强制重新扫描。

    Returns:
        CmdInfo 列表；duck-list-cmd 未安装或执行失败时返回空列表。
    """
    exe = shutil.which("duck-list-cmd")
    if not exe:
        return []

    cmd = [exe, "--jsonl"]
    if pattern:
        cmd += ["--name", pattern]
    if refresh:
        cmd.append("--refresh")

    env = dict(os.environ)
    # 子进程按 UTF-8 输出，避免 Windows 默认代码页导致中文路径乱码
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=env)
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []

    result = []
    for line in out.stdout.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = record.get("name")
        if not name:
            continue
        result.append(CmdInfo(name=name, path=record.get("path") or None))
    return result


class CommandNameLoader:
    """在后台线程加载系统命令名，供 shell 类工具的补全使用。

    list_commands 需要启动子进程（首次还可能重建缓存），直接在交互线程调用
    会造成卡顿。调用 start() 后台加载，get_names() 在加载完成前返回空列表，
    补全先用内置命令与历史命令兜底。
    """

    def __init__(self) -> None:
        self._names: List[str] = []
        self._started = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """启动后台加载（并发/重复调用只会实际加载一次）。"""
        with self._lock:
            if self._started:
                return
            self._started = True
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self) -> None:
        try:
            names = [cmd.name for cmd in list_commands()]
        except Exception:
            names = []
        # 整体替换引用，读侧无需加锁
        self._names = sorted(set(names))

    def get_names(self) -> List[str]:
        """返回已加载的命令名（未加载完成时为空列表）。"""
        return self._names

