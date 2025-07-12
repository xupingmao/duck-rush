import subprocess
import sys
import time
import argparse
import ctypes
import os
import platform
from datetime import datetime, timedelta



def prevent_sleep_windows(duration=None):
    """
    防止 Windows 系统进入睡眠状态或锁定屏幕
    
    参数:
        duration: 防止睡眠的持续时间（分钟），如果为 None 则无限期防止
    """
    try:
                
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
        if duration is not None:
            end_time = datetime.now() + timedelta(minutes=duration)
            print(f"已启动防睡眠模式，将持续 {duration} 分钟...")
        else:
            print("已启动防睡眠模式，按 Ctrl+C 停止...")
        
        # 主循环
        try:
            while True:
                # 检查是否已达到指定的持续时间
                if duration is not None and datetime.now() >= end_time:
                    break
                
                # 每5秒检查一次
                time.sleep(5)
                
                # 输出剩余时间（如果指定了持续时间）
                if duration is not None:
                    remaining = end_time - datetime.now()
                    print(f"剩余时间: {remaining.seconds // 60} 分 {remaining.seconds % 60} 秒", end='\r')
        
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

def prevent_sleep_mac(duration=None):
    """
    使用 caffeinate 命令防止 macOS 进入睡眠状态
    
    参数:
        duration: 防止睡眠的持续时间（分钟），如果为 None 则无限期防止
    """
    try:
        # 构建 caffeinate 命令
        cmd = ['caffeinate', '-d', '-i', '-m', '-u']  # 防止显示器休眠、系统休眠、磁盘休眠，并模拟用户活动
        
        if duration is not None:
            # 如果指定了持续时间，将其转换为秒并添加到命令中
            duration_sec = int(duration * 60)
            cmd.extend(['-t', str(duration_sec)])
            print(f"已启动防睡眠模式，将持续 {duration} 分钟...")
        else:
            print("已启动防睡眠模式，按 Ctrl+C 停止...")
        
        # 执行命令
        process = subprocess.Popen(cmd)
        
        # 如果没有指定持续时间，等待用户中断
        if duration is None:
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n收到停止信号，正在退出防睡眠模式...")
                process.terminate()
                process.wait()
                print("已成功退出防睡眠模式。")
        
        return process.wait()
    
    except Exception as e:
        print(f"发生错误: {e}")
        return 1
    
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