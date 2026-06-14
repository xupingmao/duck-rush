# encoding=utf-8
import argparse
import os
import subprocess
import sys


def get_current_branch():
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description="checkout出git分支")
    parser.add_argument("branch", nargs="?", default="", help="分支名称")
    args = parser.parse_args()

    if not args.branch:
        script_file = os.path.basename(sys.argv[0])
        script_name, ext = os.path.splitext(script_file)
        print(f"usage: {script_name} branchName")
        return

    current = get_current_branch()
    if current == args.branch:
        print(f"当前已经在分支 {args.branch}，跳过checkout")
        return

    os.system("git pull")
    result = os.system(f"git checkout -b {args.branch} origin/{args.branch};")
    if result != 0:
        print(f"checkout远程分支失败，尝试checkout本地分支: {args.branch}")
        os.system(f"git checkout {args.branch}")

    os.system("git pull")


if __name__ == "__main__":
    main()
