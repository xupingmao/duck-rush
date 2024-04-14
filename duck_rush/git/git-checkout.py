# encoding=utf-8
import fire
import os
import sys

def main(branch=""):
    if branch == "":
        script_file = os.path.basename(sys.argv[0])
        script_name, ext = os.path.splitext(script_file)
        print(f"usage: {script_name} branchName")
        return
    
    os.system("git pull")
    result = os.system(f"git checkout -b {branch} origin/{branch};")
    if result == 128:
        print(f"checkout远程分支失败，尝试checkout本地分支: {branch}")
        os.system(f"git checkout {branch}")

    os.system("git pull")


if __name__ == "__main__":
    fire.Fire(main)
