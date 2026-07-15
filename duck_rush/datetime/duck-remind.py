# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2026/07/15
# @modified 2026/07/15
'''
命令行提醒工具 (duck-remind)

用法:
    python duck-remind.py add <time> <message> [--snooze N]   设置提醒
    python duck-remind.py list                                列出待提醒
    python duck-remind.py remove <id>                          删除提醒
    python duck-remind.py daemon                              后台调度(内部, add 自动拉起)

时间格式:
    相对: +10s / +5m / +1h / +1d   (数字+单位)
    绝对: 14:30 / 2026-07-15 14:30 / 2026-07-15 14:30:00 / 2026/07/15 14:30 ...

说明:
    - add 仅把提醒写入数据库并立即返回, 后台守护进程到期自动弹出 GUI
    - 弹窗使用 tkinter, 置顶悬浮, 含「关闭」和「稍后提醒」两个按钮
    - 同一时刻最多只展示一个弹窗(守护进程单实例 + 顺序弹窗 + 弹窗锁)
'''
import os
import sys
import time
import json
import subprocess
import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

try:
    from duck_rush.utils.os_util import is_windows
except ImportError:
    try:
        from utils.os_util import is_windows
    except ImportError:
        def is_windows() -> bool:
            return sys.platform.startswith("win")

# ---------------------------------------------------------------------------
# 路径 & 常量
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(REPO_ROOT, "data")
REMIND_DIR = os.path.join(DATA_DIR, "remind")
REMINDERS_PATH = os.path.join(REMIND_DIR, "reminders.jsonl")
DAEMON_PID_PATH = os.path.join(REMIND_DIR, "daemon.pid")
POPUP_LOCK_PATH = os.path.join(REMIND_DIR, "popup.lock")
DAEMON_LOG_PATH = os.path.join(REMIND_DIR, "daemon.log")

DEFAULT_SNOOZE_MIN = 5          # 稍后提醒默认推迟 5 分钟
POLL_INTERVAL = 2               # 守护进程轮询间隔(秒)

# 支持的绝对时间格式
DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%H:%M:%S",
    "%H:%M",
]

# 相对时间单位换算(秒)
UNIT_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
}


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def ensure_remind_dir() -> None:
    if not os.path.isdir(REMIND_DIR):
        os.makedirs(REMIND_DIR, exist_ok=True)


def is_process_alive(pid: int) -> bool:
    """检查进程是否存活(跨平台, 不真正发送信号)"""
    if pid <= 0:
        return False
    if is_windows():
        return _win_process_alive(pid)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _win_process_alive(pid: int) -> bool:
    """Windows 下用 OpenProcess + GetExitCodeProcess 判断进程是否存活。
    os.kill(pid, 0) 在部分 Windows Python 构建上会直接崩溃, 故不使用。"""
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return exit_code.value == STILL_ACTIVE
            return False
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        # 兜底: 无法判断时保守认为存活, 避免重复拉起守护进程
        return True


def read_pid_file(path: str) -> Optional[int]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            content = f.read().strip()
        return int(content) if content else None
    except (ValueError, OSError):
        return None


# ---------------------------------------------------------------------------
# 时间解析
# ---------------------------------------------------------------------------
def parse_relative(text: str) -> Optional[float]:
    """解析相对时间, 如 +10m / 5m / +1h。返回未来时间戳, 无法解析返回 None"""
    t = text.strip()
    if t.startswith("+"):
        t = t[1:]
    # 形如 <数字><单位>
    num = ""
    unit = ""
    for ch in t:
        if ch.isdigit() or ch == ".":
            num += ch
        else:
            unit += ch
    if not num:
        return None
    unit = unit.strip().lower()
    if unit not in UNIT_SECONDS:
        return None
    try:
        delta = float(num) * UNIT_SECONDS[unit]
    except ValueError:
        return None
    return time.time() + delta


def parse_absolute(text: str) -> Optional[float]:
    """解析绝对时间字符串。返回时间戳, 无法解析返回 None"""
    t = text.strip()
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(t, fmt)
        except ValueError:
            continue
        if fmt in ("%H:%M", "%H:%M:%S"):
            # 仅时分/时分秒: 拼接今天的日期, 已过则顺延到明天
            now = datetime.now()
            dt = now.replace(hour=dt.hour, minute=dt.minute,
                             second=dt.second, microsecond=0)
            if dt <= now:
                dt += timedelta(days=1)
        return dt.timestamp()
    return None


def parse_time(text: str) -> float:
    """解析提醒时间, 先尝试相对再尝试绝对。失败抛出 ValueError"""
    text = (text or "").strip()
    if not text:
        raise ValueError("时间不能为空")
    ts = parse_relative(text)
    if ts is None:
        ts = parse_absolute(text)
    if ts is None:
        raise ValueError("无法解析时间: %r (支持 +5m / 14:30 / 2026-07-15 14:30 等)" % text)
    return ts


# ---------------------------------------------------------------------------
# 提醒数据模型 & DAO
# ---------------------------------------------------------------------------
@dataclass
class Reminder:
    """一条提醒记录"""
    message: str
    remind_time: float
    snooze_min: int = DEFAULT_SNOOZE_MIN
    status: str = "pending"          # pending / done
    created_time: float = 0.0
    id: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "message": self.message,
            "remind_time": self.remind_time,
            "snooze_min": self.snooze_min,
            "status": self.status,
            "created_time": self.created_time,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Reminder":
        return Reminder(
            id=d.get("id", 0),
            message=d.get("message", ""),
            remind_time=d.get("remind_time", 0.0),
            snooze_min=d.get("snooze_min", DEFAULT_SNOOZE_MIN),
            status=d.get("status", "pending"),
            created_time=d.get("created_time", 0.0),
        )


class ReminderDao:
    """提醒数据的 JSONL 持久化层(DAO)"""

    def __init__(self, path: str = REMINDERS_PATH) -> None:
        self.path = path

    def _read_all(self) -> List[Reminder]:
        """读取全部提醒, 跳过空行与损坏行"""
        if not os.path.exists(self.path):
            return []
        result: List[Reminder] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    result.append(Reminder.from_dict(json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    continue
        return result

    def _write_all(self, items: List[Reminder]) -> None:
        """整体重写文件(先写临时文件再原子替换, 避免半写损坏)"""
        ensure_remind_dir()
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it.to_dict(), ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)

    def add(self, remind_time: float, message: str, snooze_min: int) -> Reminder:
        items = self._read_all()
        new_id = max([it.id for it in items], default=0) + 1
        r = Reminder(
            id=new_id,
            message=message,
            remind_time=remind_time,
            snooze_min=snooze_min,
            status="pending",
            created_time=time.time(),
        )
        items.append(r)
        self._write_all(items)
        return r

    def list_all(self) -> List[Reminder]:
        return sorted(self._read_all(), key=lambda x: x.remind_time)

    def list_pending(self) -> List[Reminder]:
        return [r for r in self.list_all() if r.status == "pending"]

    def get_due(self) -> Optional[Reminder]:
        """返回最早到期的一条待提醒(无则 None)"""
        now = time.time()
        due = [r for r in self._read_all()
               if r.status == "pending" and r.remind_time <= now]
        due.sort(key=lambda x: x.remind_time)
        return due[0] if due else None

    def get_by_id(self, rid: int) -> Optional[Reminder]:
        for r in self._read_all():
            if r.id == rid:
                return r
        return None

    def update(self, rid: int, **changes: Any) -> bool:
        items = self._read_all()
        for it in items:
            if it.id == rid:
                for k, v in changes.items():
                    setattr(it, k, v)
                self._write_all(items)
                return True
        return False

    def mark_done(self, rid: int) -> None:
        self.update(rid, status="done")

    def snooze(self, rid: int, snooze_min: int) -> None:
        self.update(rid, remind_time=time.time() + snooze_min * 60)

    def remove(self, rid: int) -> bool:
        items = self._read_all()
        new_items = [it for it in items if it.id != rid]
        if len(new_items) == len(items):
            return False
        self._write_all(new_items)
        return True


# 模块级单例, 供 CLI / 守护进程共用
dao = ReminderDao()


# ---------------------------------------------------------------------------
# GUI 弹窗 (tkinter)
# ---------------------------------------------------------------------------
class RemindWindow:
    """置顶悬浮提醒弹窗, 返回 'close' 或 'snooze'"""

    def __init__(self, message: str, snooze_min: int) -> None:
        import tkinter as tk
        self.tk = tk
        self.result: Optional[str] = None

        root = tk.Tk()
        self.root = root
        root.title("提醒")
        root.resizable(False, False)

        # 置顶悬浮
        root.attributes("-topmost", True)
        root.update()
        root.lift()
        root.focus_force()

        # 窗口尺寸 & 居中偏上
        width, height = 360, 180
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = max(40, screen_h // 4)
        root.geometry("%dx%d+%d+%d" % (width, height, x, y))

        # 文案
        msg_label = tk.Label(
            root,
            text=message,
            font=("Microsoft YaHei", 13),
            wraplength=width - 40,
            justify="center",
            padx=10,
            pady=10,
        )
        msg_label.pack(expand=True, fill=tk.BOTH)

        # 按钮区
        btn_frame = tk.Frame(root)
        btn_frame.pack(side=tk.BOTTOM, pady=12)

        snooze_btn = tk.Button(
            btn_frame,
            text="稍后提醒 (%d分钟)" % snooze_min,
            width=14,
            command=self._on_snooze,
        )
        snooze_btn.pack(side=tk.LEFT, padx=8)

        close_btn = tk.Button(
            btn_frame,
            text="关闭",
            width=14,
            command=self._on_close,
        )
        close_btn.pack(side=tk.LEFT, padx=8)

        # 回车=关闭, Esc=稍后提醒
        root.bind("<Return>", lambda e: self._on_close())
        root.bind("<Escape>", lambda e: self._on_snooze())

    def _on_close(self) -> None:
        self.result = "close"
        self.root.destroy()

    def _on_snooze(self) -> None:
        self.result = "snooze"
        self.root.destroy()

    def run(self) -> str:
        self.root.mainloop()
        return self.result or "close"


def show_reminder(message: str, snooze_min: int) -> str:
    """弹出提醒窗口, 返回用户选择。GUI 不可用时回退到命令行确认"""
    try:
        return RemindWindow(message, snooze_min).run()
    except Exception as e:  # pragma: no cover - tkinter 异常兜底
        print("[提醒] %s" % message)
        print("  (GUI 不可用: %s) 输入 s 稍后提醒, 其他键关闭:" % e, end=" ", flush=True)
        try:
            ans = input().strip().lower()
        except EOFError:
            return "close"
        return "snooze" if ans == "s" else "close"


# ---------------------------------------------------------------------------
# 弹窗锁 (跨进程保证同一时刻只有一个弹窗)
# ---------------------------------------------------------------------------
def acquire_popup_lock() -> bool:
    pid = read_pid_file(POPUP_LOCK_PATH)
    if pid is not None and is_process_alive(pid):
        return False
    try:
        with open(POPUP_LOCK_PATH, "w") as f:
            f.write(str(os.getpid()))
        return True
    except OSError:
        return False


def release_popup_lock() -> None:
    try:
        if os.path.exists(POPUP_LOCK_PATH):
            os.remove(POPUP_LOCK_PATH)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 守护进程
# ---------------------------------------------------------------------------
def daemon_running() -> bool:
    pid = read_pid_file(DAEMON_PID_PATH)
    return pid is not None and is_process_alive(pid)


def write_daemon_pid() -> None:
    ensure_remind_dir()
    with open(DAEMON_PID_PATH, "w") as f:
        f.write(str(os.getpid()))


def _get_python_exe() -> str:
    """优先使用 pythonw(无控制台窗口), 回退到当前解释器"""
    exe = sys.executable
    if is_windows():
        base, _ = os.path.splitext(exe)
        pythonw = base + "w.exe"
        if os.path.exists(pythonw):
            return pythonw
    return exe


def start_daemon() -> None:
    """如果守护进程未运行则拉起一个(后台, 无控制台)"""
    if daemon_running():
        return
    script = os.path.abspath(__file__)
    python_exe = _get_python_exe()
    ensure_remind_dir()
    logf = open(DAEMON_LOG_PATH, "a", encoding="utf-8")
    try:
        if is_windows():
            DETACHED = 0x00000008 | 0x00000200  # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
            subprocess.Popen(
                [python_exe, script, "daemon"],
                stdout=logf, stderr=logf,
                creationflags=DETACHED, close_fds=True,
            )
        else:
            subprocess.Popen(
                [python_exe, script, "daemon"],
                stdout=logf, stderr=logf,
                start_new_session=True, close_fds=True,
            )
    finally:
        logf.close()


def run_daemon() -> None:
    """调度循环: 轮询到期提醒并弹出 GUI, 同一时刻只弹一个窗"""
    write_daemon_pid()
    print("[daemon] 提醒守护进程已启动 (pid=%d)" % os.getpid(), flush=True)
    try:
        while True:
            item = dao.get_due()
            if item is not None:
                if not acquire_popup_lock():
                    # 已有弹窗在进行(极端情况), 稍后再试
                    time.sleep(POLL_INTERVAL)
                    continue
                try:
                    choice = show_reminder(item.message, item.snooze_min)
                finally:
                    release_popup_lock()
                if choice == "close":
                    dao.mark_done(item.id)
                else:
                    dao.snooze(item.id, item.snooze_min)
            else:
                time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        # 退出时清理自己的 pid 文件(仅当仍是自己)
        pid = read_pid_file(DAEMON_PID_PATH)
        if pid == os.getpid():
            try:
                os.remove(DAEMON_PID_PATH)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _format_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def cmd_add(args: argparse.Namespace) -> None:
    ts = parse_time(args.time)
    r = dao.add(ts, args.message, args.snooze)
    start_daemon()
    print("已设置提醒 #%d: [%s] %s" % (r.id, _format_time(ts), args.message))
    print("  (后台守护进程将在到期时弹窗提醒)")


def cmd_list(args: argparse.Namespace) -> None:
    items = dao.list_pending()
    if not items:
        print("当前没有提醒")
        return
    print("%-4s %-19s %-6s %s" % ("ID", "时间", "状态", "文案"))
    for it in items:
        print("%-4d %-19s %-6s %s" % (
            it.id, _format_time(it.remind_time), it.status, it.message))


def cmd_remove(args: argparse.Namespace) -> None:
    if dao.remove(args.id):
        print("已删除提醒 #%d" % args.id)
    else:
        print("未找到提醒 #%d" % args.id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="命令行提醒工具")
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="设置提醒")
    p_add.add_argument("time", help="提醒时间, 如 +5m / 14:30 / 2026-07-15 14:30")
    p_add.add_argument("message", help="提醒文案")
    p_add.add_argument("--snooze", type=int, default=DEFAULT_SNOOZE_MIN,
                       help="稍后提醒推迟分钟数(默认 %d)" % DEFAULT_SNOOZE_MIN)
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="列出提醒")
    p_list.set_defaults(func=cmd_list)

    p_rm = sub.add_parser("remove", help="删除提醒")
    p_rm.add_argument("id", type=int, help="提醒 ID")
    p_rm.set_defaults(func=cmd_remove)

    p_daemon = sub.add_parser("daemon", help="后台调度(内部)")
    p_daemon.set_defaults(func=lambda a: run_daemon())

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
