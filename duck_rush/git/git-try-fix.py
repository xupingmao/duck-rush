import os
import argparse

def clean_gc_cache():
    os.system("git gc --prune=now")


def rm_lock_file():
    pathlist = []
    for root, dirs, files in os.walk(".git"):
        for fname in files:
            if fname.endswith(".lock"):
                fpath = os.path.join(root, fname)
                pathlist.append(fpath)
    
    if len(pathlist) == 0:
        return
    
    print("扫描出下列lock文件:")
    for index, fpath in enumerate(pathlist, start=1):
        print(f"{index} {fpath}")
    result = input("确认删除吗? (Y/N)\n")
    if result.upper() == "Y":
        for fpath in pathlist:
            os.remove(fpath)


def fix_git(args: argparse.Namespace):
    clean_gc_cache()
    rm_lock_file()

_help_msg = """修复git工具,会尝试如下操作
1. 清理git缓存
2. 删除lock文件
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=_help_msg)
    args = parser.parse_args()
    fix_git(args)
