# encoding=utf-8
import os
import subprocess
import termcolor


def print_error(msg):
    print(termcolor.colored("ERR:" + msg, "red"))


def popen(cmd) -> str:
    proc = subprocess.Popen(cmd,
                            shell=True,
                            stdout=subprocess.PIPE)
    with proc:
        assert proc.stdout is not None
        return proc.stdout.read().decode("utf-8")


def check_branch():
    current = popen("git branch")
    if current.strip() != "* master":
        print_error("当前不是master分支, 请切换到master分支")
        return False
    return True


def main():
    """强制从master分支同步"""
    if not check_branch():
        return
    os.system("git fetch --all")
    os.system("git reset --hard origin/master")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print('强制从 origin/master 同步当前分支 (git fetch --all && git reset --hard origin/master)')
        sys.exit(0)
    main()
