
"""
Fix USB flash drive
修复USB工具
支持文件格式
- FAT32
"""

import os
import sys
import platform
import subprocess


def fix_usb_flash(drive_letter):
    """
    修复USB闪存驱动器
    :param drive_letter: 驱动器盘符，例如 "E:" (Windows) 或 "/dev/sdb1" (Linux)
    :return: 修复结果
    """
    system = platform.system()
    
    if system == "Windows":
        # Windows系统使用chkdsk命令
        if not drive_letter.endswith(":"):
            drive_letter += ":"
        
        print(f"正在修复Windows系统上的驱动器 {drive_letter}...")
        try:
            # 使用chkdsk命令修复文件系统，/f参数表示修复错误
            result = subprocess.run(
                ["chkdsk", drive_letter, "/f"],
                capture_output=True,
                text=True,
                check=False
            )
            
            print("修复完成！")
            print("输出结果:")
            print(result.stdout)
            
            if result.stderr:
                print("错误信息:")
                print(result.stderr)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"修复过程中出错: {e}")
            return False
            
    elif system == "Linux":
        # Linux系统使用fsck命令
        print(f"正在修复Linux系统上的驱动器 {drive_letter}...")
        try:
            # 使用fsck命令修复FAT32文件系统
            result = subprocess.run(
                ["sudo", "fsck", "-y", drive_letter],
                capture_output=True,
                text=True,
                check=False
            )
            
            print("修复完成！")
            print("输出结果:")
            print(result.stdout)
            
            if result.stderr:
                print("错误信息:")
                print(result.stderr)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"修复过程中出错: {e}")
            return False
            
    else:
        print(f"不支持的操作系统: {system}")
        return False


def list_drives():
    """
    列出系统中的驱动器
    :return: 驱动器列表
    """
    system = platform.system()
    drives = []
    
    if system == "Windows":
        # Windows系统使用wmic命令列出驱动器
        try:
            result = subprocess.run(
                ["wmic", "logicaldisk", "get", "DeviceID,MediaType"],
                capture_output=True,
                text=True,
                check=False
            )
            
            lines = result.stdout.strip().split('\n')[1:]
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] == "Removable Disk":
                    drives.append(parts[0])
                    
        except Exception as e:
            print(f"列出驱动器时出错: {e}")
            
    elif system == "Linux":
        # Linux系统使用lsblk命令列出驱动器
        try:
            result = subprocess.run(
                ["lsblk", "-o", "NAME,TYPE,MOUNTPOINT"],
                capture_output=True,
                text=True,
                check=False
            )
            
            lines = result.stdout.strip().split('\n')[1:]
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] == "part" and "sd" in parts[0]:
                    drives.append(f"/dev/{parts[0]}")
                    
        except Exception as e:
            print(f"列出驱动器时出错: {e}")
            
    return drives


def main():
    """
    主函数
    """
    print("=== Duck Fix USB Flash 工具 ===")
    print("用于修复损坏的FAT32 U盘文件系统")
    print("\n")
    
    # 列出可用的驱动器
    drives = list_drives()
    
    if not drives:
        print("未检测到可移动驱动器")
        return
    
    print("检测到以下可移动驱动器:")
    for i, drive in enumerate(drives, 1):
        print(f"{i}. {drive}")
    
    # 让用户选择要修复的驱动器
    try:
        choice = int(input("\n请选择要修复的驱动器编号: "))
        if 1 <= choice <= len(drives):
            drive_to_fix = drives[choice - 1]
            print(f"\n您选择了: {drive_to_fix}")
            
            # 执行修复
            success = fix_usb_flash(drive_to_fix)
            
            if success:
                print("\n修复成功！")
            else:
                print("\n修复失败，请检查错误信息。")
                
        else:
            print("无效的选择")
            
    except ValueError:
        print("请输入有效的数字")


if __name__ == "__main__":
    main()

