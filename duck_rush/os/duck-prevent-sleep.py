import subprocess
import sys
import time
import argparse
import ctypes
import os
import platform
from typing import Optional
from datetime import datetime, timedelta

DEFAULT_DURATION = 60 * 24 * 100 # minutes
SLEEP_INTERVAL = 1 # 单位秒


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

def prevent_sleep_windows(duration: Optional[float]=None):
    """
    防止 Windows 系统进入睡眠状态或锁定屏幕
    
    参数:
        duration: 防止睡眠的持续时间（分钟），如果为 None 则无限期防止
    """
    try:
        
        if duration is None:
            duration = DEFAULT_DURATION
                
        # 导入 Windows API 常量和函数
        ES_CONTINUOUS = 0x80000000
        ES_DISPLAY_REQUIRED = 0x00000002
        ES_SYSTEM_REQUIRED = 0x00000001

        SetThreadExecutionState = ctypes.windll.kernel32.SetThreadExecutionState

        # 设置执行状态，防止系统休眠和屏幕关闭
        result = SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED)
        if not result:
            raise RuntimeError("无法设置系统执行状态")
        
        # 计算结束时间（如果指定了持续时间）
        end_time = datetime.now() + timedelta(minutes=duration)
        print(f"已启动防睡眠模式，将持续 {duration} 分钟"
              f"（{format_duration_minutes(duration)}）, 按 Ctrl+C 停止...")
        
        # 主循环
        try:
            while True:
                # 检查是否已达到指定的持续时间
                if datetime.now() >= end_time:
                    break
                
                # 间隔检查一次
                time.sleep(SLEEP_INTERVAL)
                
                # 输出剩余时间（如果指定了持续时间）
                remaining = (end_time - datetime.now()).total_seconds()
                line = f"剩余时间: {format_remaining(remaining)}"
                # 补空格覆盖上一次更长的输出，避免残留字符
                print(f"\r{line.ljust(40)}", end='', flush=True)
        
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

def prevent_sleep_mac(duration:Optional[float]=None):
    """
    使用 caffeinate 命令防止 macOS 进入睡眠状态
    
    参数:
        duration: 防止睡眠的持续时间（分钟），如果为 None 则无限期防止
    """
    if duration is None:
        duration = DEFAULT_DURATION

    process:Optional[subprocess.Popen] = None
    try:
        # 构建 caffeinate 命令（后台运行，不带 -t 由自己控制时长）
        cmd = ['caffeinate', '-d', '-i', '-m', '-u']
        print(f"已启动防睡眠模式，将持续 {duration} 分钟"
              f"（{format_duration_minutes(duration)}）, 按 Ctrl+C 停止...")

        # 后台启动 caffeinate
        process = subprocess.Popen(cmd)

        end_time = datetime.now() + timedelta(minutes=duration)

        while True:
            if datetime.now() >= end_time:
                break

            time.sleep(SLEEP_INTERVAL)

            remaining = (end_time - datetime.now()).total_seconds()
            line = f"剩余时间: {format_remaining(remaining)}"
            # 补空格覆盖上一次更长的输出，避免残留字符
            print(f"\r{line.ljust(40)}", end='', flush=True)

    except KeyboardInterrupt:
        print("\n收到停止信号，正在退出防睡眠模式...")
    except Exception as e:
        print(f"发生错误: {e}")
        return 1
    finally:
        if process:
            process.terminate()
            process.wait()
        print("已成功退出防睡眠模式。")
    
def prevent_sleep(duration=None):
    if os.name == "nt":
        return prevent_sleep_windows(duration)
    if platform.system() == "Darwin":
        return prevent_sleep_mac(duration)
    print("不支持的操作系统", file=sys.stderr)
    return 1

if __name__ == "__main__":
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description="防止 macOS 屏幕锁定和系统睡眠")
    parser.add_argument("-d", "--duration", type=float, help="指定防睡眠的持续时间（分钟）")
    
    args = parser.parse_args()
    
    # 运行防睡眠函数
    sys.exit(prevent_sleep(args.duration))    