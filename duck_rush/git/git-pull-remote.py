# encoding=utf-8
import os
import fire

def main():
    current=os.popen("git symbolic-ref --short -q HEAD").read().strip()
    os.system(f"git pull origin {current}")


if __name__ == "__main__":
    fire.Fire(main)
    