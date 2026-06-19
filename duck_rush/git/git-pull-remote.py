# encoding=utf-8
import os

def main():
    current=os.popen("git symbolic-ref --short -q HEAD").read().strip()
    os.system(f"git pull origin {current}")


if __name__ == "__main__":
    main()
    