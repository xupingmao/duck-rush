"""防止 macOS/Windows 系统进入睡眠状态

默认行为：只阻止系统休眠，**允许屏幕息屏**；
加上 `-s`/`--screen` 后额外阻止屏幕关闭（保持常亮）。

用法:
    duck-prevent-sleep [-h] [-d DURATION] [-s]
"""

import subprocess
import sys
import time
import argparse
import ctypes
import os
import platform
from typing import List, Optional
from datetime import datetime, timedelta

DEFAULT_DURATION = 60 * 24 * 100 # minutes
SLEEP_INTERVAL = 1 # 单位秒

# Windows API 执行状态标志
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


def format_remaining(seconds: float) -> str:
    """
    将剩余秒数格式化为可读文本

    注意：必须使用 total_seconds()，timedelta.seconds 只表示「天以内」的零头，
    超过 1 天时会丢失天数导致倒计时显示错误。

    参数:
        seconds: 剩余秒数（负数会被截断为 0）

    返回:
        形如 "99 天 23:59:12"（超过一天）或 "23:59:12"（一天以内）的文本
    """
    total = max(0, int(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days > 0:
        return f"{days} 天 {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_duration_minutes(minutes: float) -> str:
    """将分钟数格式化为可读文本，例如 144000 -> "100 天 00:00:00" """
    return format_remaining(minutes * 60)


def windows_execution_flags(keep_screen: bool) -> int:
    """
    构造 SetThreadExecutionState 的标志位

    参数:
        keep_screen: 为 True 时附加 ES_DISPLAY_REQUIRED 阻止息屏，
                     为 False 时只阻止系统休眠、允许屏幕息屏
    """
    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    if keep_screen:
        flags |= ES_DISPLAY_REQUIRED
    return flags


def mac_caffeinate_args(keep_screen: bool) -> List[str]:
    """
    构造 caffeinate 命令参数

    参数:
        keep_screen: 为 True 时附加 -d/-u 阻止显示器睡眠，
                     为 False 时只阻止系统休眠（-i）、允许屏幕息屏
    """
    if keep_screen:
        return ['caffeinate', '-d', '-i', '-m', '-u']
    return ['caffeinate', '-i', '-m']


def print_banner(duration: float, keep_screen: bool) -> None:
    """打印启动信息，明确当前是否阻止息屏"""
    screen_desc = "阻止屏幕息屏" if keep_screen else "允许屏幕息屏"
    print(f"已启动防睡眠模式（{screen_desc}），将持续 {duration} 分钟"
          f"（{format_duration_minutes(duration)}）, 按 Ctrl+C 停止...")


def countdown(end_time: datetime, interval: float = SLEEP_INTERVAL) -> None:
    """
    倒计时等待直到 end_time，持续打印剩余时间

    参数:
        end_time: 结束时刻
        interval: 检查间隔（秒）
    """
    while True:
        # 检查是否已达到指定的持续时间
        if datetime.now() >= end_time:
            break

        # 间隔检查一次
        time.sleep(interval)

        # 输出剩余时间（如果指定了持续时间）
        remaining = (end_time - datetime.now()).total_seconds()
        line = f"剩余时间: {format_remaining(remaining)}"
        # 补空格覆盖上一次更长的输出，避免残留字符
        print(f"\r{line.ljust(40)}", end='', flush=True)

def prevent_sleep_windows(duration: Optional[float]=None, keep_screen: bool=False) -> int:
    """
    防止 Windows 系统进入睡眠状态或锁定屏幕

    参数:
        duration: 防止睡眠的持续时间（分钟），如果为 None 则无限期防止
        keep_screen: 是否同时阻止屏幕息屏，默认 False（允许息屏）
    """
    try:
        
        if duration is None:
            duration = DEFAULT_DURATION
                
        # 导入 Windows API 函数
        SetThreadExecutionState = ctypes.windll.kernel32.SetThreadExecutionState

        # 设置执行状态，默认防止系统休眠且允许屏幕息屏；
        # 开启 keep_screen 时附加 ES_DISPLAY_REQUIRED 防止屏幕关闭
        result = SetThreadExecutionState(windows_execution_flags(keep_screen))
        if not result:
            raise RuntimeError("无法设置系统执行状态")
        
        # 计算结束时间（如果指定了持续时间）
        end_time = datetime.now() + timedelta(minutes=duration)
        print_banner(duration, keep_screen)
        
        # 主循环
        try:
            countdown(end_time)
        
        except KeyboardInterrupt:
            print("\n收到停止信号，正在退出防睡眠模式...")
        
        finally:
            # 恢复默认的系统行为
            SetThreadExecutionState(ES_CONTINUOUS)
            print("已成功退出防睡眠模式。")
        
        return 0
    
    except Exception as e:
        print(f"发生错误: {e}")
        return 1

def prevent_sleep_mac(duration:Optional[float]=None, keep_screen: bool=False) -> int:
    """
    使用 caffeinate 命令防止 macOS 进入睡眠状态

    参数:
        duration: 防止睡眠的持续时间（分钟），如果为 None 则无限期防止
        keep_screen: 是否同时阻止屏幕息屏，默认 False（允许息屏）
    """
    if duration is None:
        duration = DEFAULT_DURATION

    process:Optional[subprocess.Popen] = None
    try:
        # 构建 caffeinate 命令（后台运行，不带 -t 由自己控制时长）
        cmd = mac_caffeinate_args(keep_screen)
        print_banner(duration, keep_screen)

        # 后台启动 caffeinate
        process = subprocess.Popen(cmd)

        end_time = datetime.now() + timedelta(minutes=duration)
        countdown(end_time)

        return 0

    except KeyboardInterrupt:
        print("\n收到停止信号，正在退出防睡眠模式...")
        return 0
    except Exception as e:
        print(f"发生错误: {e}")
        return 1
    finally:
        if process:
            process.terminate()
            process.wait()
        print("已成功退出防睡眠模式。")
    
def prevent_sleep(duration: Optional[float]=None, keep_screen: bool=False) -> int:
    if os.name == "nt":
        return prevent_sleep_windows(duration, keep_screen)
    if platform.system() == "Darwin":
        return prevent_sleep_mac(duration, keep_screen)
    print("不支持的操作系统", file=sys.stderr)
    return 1

if __name__ == "__main__":
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(
        description="防止 macOS/Windows 系统睡眠（默认只允许息屏，加 -s 阻止屏幕息屏）")
    parser.add_argument("-d", "--duration", type=float, help="指定防睡眠的持续时间（分钟）")
    parser.add_argument("-s", "--screen", "--keep-screen", action="store_true",
                        help="同时阻止屏幕息屏/关闭（默认允许息屏）")
    
    args = parser.parse_args()
    
    # 运行防睡眠函数
    sys.exit(prevent_sleep(args.duration, args.screen))    
