# encoding=utf-8
import os

def main():
    current=os.popen("git symbolic-ref --short -q HEAD").read().strip()
    os.system(f"git pull origin {current}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print('从远程仓库拉取当前分支的更新 (git pull origin <当前分支>)')
        sys.exit(0)
    main()
    