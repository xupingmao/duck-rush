import os
import sys
import shutil

sources_list_file = "/etc/apt/sources.list"

aliyun_source = """# aliyun
deb http://mirrors.aliyun.com/ubuntu/ lunar main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ lunar main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ lunar-security main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ lunar-security main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ lunar-updates main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ lunar-updates main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ lunar-proposed main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ lunar-proposed main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ lunar-backports main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ lunar-backports main restricted universe multiverse
"""

def is_posix_system():
    """检查当前系统是否为 POSIX 兼容系统"""
    return os.name == 'posix'

def is_root():
    """检查当前是否具有 root 权限"""
    return os.geteuid() == 0

def run_with_root():
    """以 root 权限重新运行当前脚本"""

    if not is_posix_system():
        print("错误：此脚本仅支持 POSIX 兼容系统（如 Linux、macOS）")
        sys.exit(1)
    
    if not is_root():
        print("需要 root 权限执行此操作，正在请求 sudo...")
        # 使用 sudo 重新运行当前脚本
        args = ['sudo', sys.executable] + sys.argv
        os.execvp('sudo', args)  # 替换当前进程为 sudo 进程

def main():
    # backup file
    shutil.copyfile(sources_list_file, sources_list_file + ".bak")
    with open(sources_list_file, mode="w+", encoding="utf-8") as fp:
        fp.write(aliyun_source)


if __name__ == "__main__":
    main()