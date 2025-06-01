import os
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

def main():
    # backup file
    shutil.copyfile(sources_list_file, sources_list_file + ".bak")
    with open(sources_list_file, mode="w+", encoding="utf-8") as fp:
        fp.write(aliyun_source)


if __name__ == "__main__":
    main()