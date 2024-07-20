# encoding=utf-8

import os
import sys
import fire

def main(old_path="", new_path=""):
    if not os.path.exists(old_path):
        print(f"源文件不存在: {old_path}")
        sys.exit(1)
    
    if os.path.exists(new_path):
        print(f"目标文件已经存在: {new_path}")
        sys.exit(1)
    
    os.rename(old_path, new_path)
    print("重命名完成!")

if __name__ == "__main__":
    fire.Fire(main)
