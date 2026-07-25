# -*- coding: utf-8 -*-
"""
跨平台伪终端(pty)封装。

目的：让子进程以为自己连着真实终端，从而输出 ANSI 颜色（grep --color / ls --color
等只在检测到 TTY 时才上色）。duck-shell 原本用管道(PIPE)捕获输出，子进程检测到非
终端就不会上色，因此需要 pty。

- Unix(Linux/macOS)：使用标准库 pty。
- Windows：使用系统自带的 ConPTY（Windows 10 1809+，通过 ctypes 调用）。
- 任何平台若 pty 初始化失败，调用方应回退到普通管道捕获（见 duck-shell.py）。
"""
import os
import sys
import asyncio
import subprocess
import ctypes
from ctypes import wintypes
from typing import Optional, Dict, Any

from duck_utils.os_util import is_windows

_READ_CHUNK = 4096

# Windows ConPTY 相关常量
_PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
_EXTENDED_STARTUPINFO_PRESENT = 0x00080000
_STARTF_USESTDHANDLES = 0x00000100
_INF_INITE = 0xFFFFFFFF


class PtyProcess:
    """跨平台 pty 子进程封装。

    用法：
        proc = PtyProcess(cmd, cwd, env)
        await proc.start()
        while True:
            raw = await proc.read_chunk(4096)
            if not raw:
                break
            ... 处理 raw ...
        await proc.wait()
        proc.close()
    """

    def __init__(self, cmd: str, cwd: Optional[str], env: Optional[Dict[str, str]]) -> None:
        self.cmd: str = cmd
        self.cwd: Optional[str] = cwd
        self.env: Optional[Dict[str, str]] = env
        self.read_fd: Optional[int] = None
        # Unix 分支持有 asyncio 子进程对象
        self._unix_proc: Optional["asyncio.subprocess.Process"] = None
        # Windows 分支持有的资源（见 _start_conpty 返回的字典）
        self._win: Optional[Dict[str, Any]] = None
        self.returncode: Optional[int] = None

    async def start(self) -> None:
        if is_windows():
            self._win = _start_conpty(self.cmd, self.cwd, self.env)
            self.read_fd = self._win["out_fd"]
        else:
            await self._start_unix()

    async def _start_unix(self) -> None:
        import pty  # 仅 Unix 可用
        master, slave = pty.openpty()  # type: ignore[attr-defined]
        self.read_fd = master
        # 仅把标准输出/错误接到 pty（grep/ls 会以为连着终端而上色），
        # 标准输入用 DEVNULL 以立即给子进程 EOF，避免其等待输入而卡住。
        self._unix_proc = await asyncio.create_subprocess_shell(
            self.cmd,
            cwd=self.cwd,
            env=self.env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=slave,
            stderr=slave,
        )
        os.close(slave)

    def send_eof(self) -> None:
        """向伪终端输入写入 Ctrl-D(0x04) 以产生 EOF，让等待标准输入的子进程（如 msys
        的 cat/grep）正常结束，而不会因为输入管道一直打开却无数据而挂死。
        注意：不要直接关闭输入写端，那会让 conhost 误判终端断开并发送 Ctrl-C。"""
        if self._win is None:
            return
        api = self._win["api"]
        in_write = self._win["in_write"]
        buf = ctypes.create_string_buffer(b"\x04", 1)
        n = wintypes.DWORD(0)
        try:
            api["WriteFile"](in_write, buf, 1, ctypes.byref(n), None)
        except Exception:
            pass

    def kill(self) -> None:
        """强制结束子进程（用于超时/卡死兜底）。"""
        if self._win is not None:
            api = self._win["api"]
            try:
                api["kernel32"].TerminateProcess(self._win["hProcess"], 1)
            except Exception:
                pass
        elif self._unix_proc is not None and self._unix_proc.returncode is None:
            try:
                self._unix_proc.kill()
            except ProcessLookupError:
                pass

    async def read_chunk(self, size: int = _READ_CHUNK) -> Optional[bytes]:
        """读取一块输出。

        返回：
        - 字节串：读取到的数据（可能是 b"" 表示 EOF）
        - None：Windows 下当前无可读数据且进程仍在运行（调用方应稍后重试）
        """
        loop = asyncio.get_running_loop()
        if self._win is not None:
            return await loop.run_in_executor(None, self._win_read, size)
        assert self.read_fd is not None
        return await loop.run_in_executor(None, os.read, self.read_fd, size)

    def _win_read(self, size: int) -> Optional[bytes]:
        """Windows(ConPTY) 下的读取。

        ConPTY 的已知坑：
          1) 子进程退出后，ConPTY 仍保持输出管道写端打开，os.read 收不到 EOF 而阻塞；
          2) WaitForMultipleObjects 会"伪信号"输出管道（声称可读但 os.read 实际会阻塞）。

        因此这里：
          - 先判进程是否已退出（WaitForSingleObject(hProcess,0)）；退出则排空剩余缓冲返回 EOF；
          - 否则用 PeekNamedPipe 探查"真正可读的字节数"，有数据才 os.read，绝不在
            伪信号上阻塞；无数据则视进程状态返回 b""(EOF) 或 None(稍后重试)。
        """
        assert self._win is not None
        api = self._win["api"]
        h_process = self._win["hProcess"]
        out_handle = self._win["out_handle"]
        assert self.read_fd is not None
        # 1) 进程是否已经退出？退出则排空剩余输出后判定 EOF
        if api["WaitForSingleObject"](h_process, 0) == 0:
            return self._win_drain()
        # 2) 进程仍在运行：探查真实可读字节数，避免 os.read 在伪信号上阻塞
        avail = wintypes.DWORD(0)
        if api["PeekNamedPipe"](out_handle, None, 0, None,
                                 ctypes.byref(avail), None):
            if avail.value > 0:
                try:
                    data = os.read(self.read_fd, min(size, avail.value))
                except OSError:
                    return b""
                if not data:
                    return b""
                return data
            # 管道可用但当前无字节：进程还活着，稍后重试
            return None
        # PeekNamedPipe 失败：管道已关闭 → EOF
        return b""

    def _win_drain(self) -> bytes:
        """进程退出后排空输出管道剩余字节（用 PeekNamedPipe 判定，绝不阻塞）。"""
        assert self._win is not None
        assert self.read_fd is not None
        api = self._win["api"]
        out_handle = self._win["out_handle"]
        buf = bytearray()
        while True:
            avail = wintypes.DWORD(0)
            if not api["PeekNamedPipe"](out_handle, None, 0, None,
                                         ctypes.byref(avail), None):
                break  # 管道已关闭
            if avail.value == 0:
                break  # 无剩余数据
            try:
                chunk = os.read(self.read_fd, min(_READ_CHUNK, avail.value))
            except OSError:
                break
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    async def wait(self) -> Optional[int]:
        if self._unix_proc is not None:
            self.returncode = await self._unix_proc.wait()
        elif self._win is not None:
            self.returncode = await asyncio.get_running_loop().run_in_executor(
                None, self._win_wait
            )
        return self.returncode

    def _win_wait(self) -> int:
        assert self._win is not None
        api = self._win["api"]
        api["WaitForSingleObject"](self._win["hProcess"], _INF_INITE)
        code = wintypes.DWORD()
        api["GetExitCodeProcess"](self._win["hProcess"], ctypes.byref(code))
        return int(code.value)

    def close(self) -> None:
        if self.read_fd is not None:
            try:
                os.close(self.read_fd)
            except OSError:
                pass
            self.read_fd = None
        if self._unix_proc is not None and self._unix_proc.returncode is None:
            try:
                self._unix_proc.kill()
            except ProcessLookupError:
                pass
        if self._win is not None:
            _win_close(self._win)


# --------------------------------------------------------------------------- #
# Windows ConPTY 实现（ctypes，懒加载并缓存）
# --------------------------------------------------------------------------- #
_conpty_api: Optional[Dict[str, Any]] = None


def _get_conpty_api() -> Dict[str, Any]:
    """加载并缓存 ConPTY 所需的 Windows API 与结构体。非 Windows / 旧系统会抛异常。"""
    global _conpty_api
    if _conpty_api is not None:
        return _conpty_api

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ole32 = ctypes.WinDLL("ole32")

    class SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", ctypes.c_void_p),
            ("bInheritHandle", wintypes.BOOL),
        ]

    class COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", ctypes.c_ushort),
            ("cbReserved2", ctypes.c_ushort),
            ("lpReserved2", ctypes.c_char_p),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class STARTUPINFOEXW(ctypes.Structure):
        _fields_ = [
            ("StartupInfo", STARTUPINFOW),
            ("lpAttributeList", ctypes.c_void_p),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]

    create_pipe = kernel32.CreatePipe
    create_pipe.argtypes = [
        ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE),
        ctypes.POINTER(SECURITY_ATTRIBUTES), wintypes.DWORD,
    ]
    create_pipe.restype = wintypes.BOOL

    create_pseudo_console = kernel32.CreatePseudoConsole
    create_pseudo_console.argtypes = [
        COORD, wintypes.HANDLE, wintypes.HANDLE, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    create_pseudo_console.restype = ctypes.HRESULT

    close_pseudo_console = kernel32.ClosePseudoConsole
    close_pseudo_console.argtypes = [ctypes.c_void_p]

    create_process_w = kernel32.CreateProcessW
    create_process_w.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR,
        ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL,
        wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFOEXW), ctypes.POINTER(PROCESS_INFORMATION),
    ]
    create_process_w.restype = wintypes.BOOL

    init_attr_list = kernel32.InitializeProcThreadAttributeList
    init_attr_list.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    init_attr_list.restype = wintypes.BOOL

    update_attr_list = kernel32.UpdateProcThreadAttribute
    update_attr_list.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, ctypes.c_ulonglong,
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    update_attr_list.restype = wintypes.BOOL

    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait_for_single_object.restype = wintypes.DWORD

    wait_for_multiple = kernel32.WaitForMultipleObjects
    wait_for_multiple.argtypes = [
        wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p),
        wintypes.BOOL, wintypes.DWORD,
    ]
    wait_for_multiple.restype = wintypes.DWORD

    get_exit_code = kernel32.GetExitCodeProcess
    get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    get_exit_code.restype = wintypes.BOOL

    peek_named_pipe = kernel32.PeekNamedPipe
    peek_named_pipe.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
    ]
    peek_named_pipe.restype = wintypes.BOOL

    write_file = kernel32.WriteFile
    write_file.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    write_file.restype = wintypes.BOOL

    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    _conpty_api = {
        "kernel32": kernel32,
        "ole32": ole32,
        "SECURITY_ATTRIBUTES": SECURITY_ATTRIBUTES,
        "COORD": COORD,
        "STARTUPINFOW": STARTUPINFOW,
        "STARTUPINFOEXW": STARTUPINFOEXW,
        "PROCESS_INFORMATION": PROCESS_INFORMATION,
        "CreatePipe": create_pipe,
        "CreatePseudoConsole": create_pseudo_console,
        "ClosePseudoConsole": close_pseudo_console,
        "CreateProcessW": create_process_w,
        "InitializeProcThreadAttributeList": init_attr_list,
        "UpdateProcThreadAttribute": update_attr_list,
        "WaitForSingleObject": wait_for_single_object,
        "WaitForMultipleObjects": wait_for_multiple,
        "GetExitCodeProcess": get_exit_code,
        "PeekNamedPipe": peek_named_pipe,
        "WriteFile": write_file,
        "CloseHandle": close_handle,
    }
    return _conpty_api


def _start_conpty(cmd: str, cwd: Optional[str], env: Optional[Dict[str, str]]) -> Dict[str, Any]:
    """在 Windows 上通过 ConPTY 启动进程，返回需被管理的资源字典。

    若 ConPTY 不可用则抛异常，由调用方回退到普通管道。
    """
    api = _get_conpty_api()
    import msvcrt

    # CreatePseudoConsole 需要调用线程处于多线程单元(MTA)
    try:
        api["ole32"].CoInitializeEx(None, 0x0)  # COINIT_MULTITHREADED
    except Exception:
        pass

    SA = api["SECURITY_ATTRIBUTES"]
    sa = SA()
    sa.nLength = ctypes.sizeof(SA)
    sa.bInheritHandle = True

    h_out_read = wintypes.HANDLE()
    h_out_write = wintypes.HANDLE()
    if not api["CreatePipe"](ctypes.byref(h_out_read), ctypes.byref(h_out_write),
                              ctypes.byref(sa), 0):
        raise ctypes.WinError(ctypes.get_last_error())

    h_in_read = wintypes.HANDLE()
    h_in_write = wintypes.HANDLE()
    if not api["CreatePipe"](ctypes.byref(h_in_read), ctypes.byref(h_in_write),
                              ctypes.byref(sa), 0):
        raise ctypes.WinError(ctypes.get_last_error())

    # 子进程的"真实"标准输入：用 NUL（立即 EOF）。
    # 目的：msys/GNU 程序若把标准输入接到伪终端，会因等待终端输入而挂死或不出输出；
    #       此处让子进程拿到一个立即 EOF 的 stdin（不挂起），而其 stdout 仍走伪终
    #       端（保持 TTY，从而上色）。注意：ConPTY 本身的输入(下方 h_in_read)保持为
    #       一条"打开的"管道且不写数据，避免 conhost 误判终端断开而发送 Ctrl-C。
    nul_fd = os.open("NUL", os.O_RDONLY)
    h_nul = wintypes.HANDLE(msvcrt.get_osfhandle(nul_fd))
    api["kernel32"].SetHandleInformation(h_nul, 0x00000001, 0x00000001)  # 设为可继承

    # 伪终端尺寸给大一些，避免子进程在 pty 宽度处额外折行
    size = api["COORD"](200, 50)
    h_pc = ctypes.c_void_p()
    hr = api["CreatePseudoConsole"](size, h_in_read, h_out_write, 0, ctypes.byref(h_pc))
    if hr != 0:
        raise OSError("CreatePseudoConsole 失败: HRESULT 0x%08x" % hr)

    # 构造属性列表并写入伪终端句柄
    size_t = ctypes.c_size_t(0)
    api["InitializeProcThreadAttributeList"](None, 1, 0, ctypes.byref(size_t))
    attr_list = ctypes.create_string_buffer(size_t.value)
    if not api["InitializeProcThreadAttributeList"](attr_list, 1, 0, ctypes.byref(size_t)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not api["UpdateProcThreadAttribute"](
            attr_list, 0, _PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
            h_pc, ctypes.sizeof(ctypes.c_void_p), None, None):
        raise ctypes.WinError(ctypes.get_last_error())

    si = api["STARTUPINFOEXW"]()
    si.StartupInfo.cb = ctypes.sizeof(api["STARTUPINFOEXW"])
    si.lpAttributeList = ctypes.cast(attr_list, ctypes.c_void_p)
    # 将子进程的标准输入/输出/错误定向到伪终端。
    # 关键：仅设置 PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE 不足以让子进程把 stdout
    # 写入管道——它仍会继承父进程的真实控制台。必须配合 STARTF_USESTDHANDLES
    # 与 bInheritHandles=TRUE，子进程才会把输出写到 h_out_write（从而被我们读取）。
    si.StartupInfo.dwFlags = _STARTF_USESTDHANDLES
    si.StartupInfo.hStdInput = h_nul
    si.StartupInfo.hStdOutput = h_out_write
    si.StartupInfo.hStdError = h_out_write
    pi = api["PROCESS_INFORMATION"]()

    cmdline = "cmd.exe /c " + cmd
    cmdline_w = ctypes.create_unicode_buffer(cmdline)

    if not api["CreateProcessW"](
            None, cmdline_w, None, None, True,
            _EXTENDED_STARTUPINFO_PRESENT, None, cwd,
            ctypes.byref(si), ctypes.byref(pi)):
        raise ctypes.WinError(ctypes.get_last_error())

    # 关闭"已被子进程继承"的那一端拷贝（见微软官方 ConPTY 示例）：
    #   - h_out_write：ConPTY 写入输出的一端，父进程不再需要，关闭之
    #   - h_in_read：ConPTY 读取输入的一端，父进程不再需要，关闭之
    # 注意：h_in_write（父进程向伪终端写输入的一端）必须保留！若在此关闭，
    #       ConPTY/conhost 会认为终端已断开，向子进程发送 Ctrl-C，导致子进程
    # 关闭"已被子进程继承"的那一端拷贝：
    #   - h_out_write：ConPTY 写入输出的一端，父进程不再需要，关闭之
    #   - h_in_read：ConPTY 读取输入的一端，父进程不再需要，关闭之
    # 注意：h_in_write（父进程向伪终端写输入的一端）必须保留！若在此关闭，
    #       ConPTY/conhost 会认为终端已断开，向子进程发送 Ctrl-C，导致子进程
    #       以 CONTROL_C_EXIT(0xC000013A) 立即退出。它在 _win_close 时关闭。
    #       需要向子进程发送 EOF 时调用 send_eof()（写入 Ctrl-D），不关闭管道。
    api["CloseHandle"](h_out_write)
    api["CloseHandle"](h_in_read)
    api["CloseHandle"](pi.hThread)

    assert h_out_read.value is not None
    out_fd = msvcrt.open_osfhandle(h_out_read.value, os.O_RDONLY)

    return {
        "out_fd": out_fd,
        # 原始输出句柄（int 值），用于 PeekNamedPipe 轮询可读性
        "out_handle": h_out_read.value,
        # 原始输入写端（保留，供 send_eof / 关闭），见上方说明
        "in_write": h_in_write,
        # NUL 输入 fd，需保持打开（关闭即关闭底层句柄），在 _win_close 中清理
        "nul_fd": nul_fd,
        "hProcess": pi.hProcess,
        "hPC": h_pc,
        "api": api,
        # 保持引用，防止 attr_list / si 被 GC 回收
        "_attr_list": attr_list,
        "_si": si,
    }


def _win_close(res: Dict[str, Any]) -> None:
    api = res["api"]
    try:
        api["ClosePseudoConsole"](res["hPC"])
    except Exception:
        pass
    # 此时子进程已退出（close 在 wait 之后调用），关闭输入写端不会触发 Ctrl-C
    for key in ("hProcess", "in_write"):
        h = res.get(key)
        if h:
            try:
                api["CloseHandle"](h)
            except Exception:
                pass
    nul_fd = res.get("nul_fd")
    if nul_fd is not None:
        try:
            os.close(nul_fd)
        except OSError:
            pass
