# encoding=utf-8

import argparse
import os
import sys

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
    parser = argparse.ArgumentParser(description='重命名/移动文件')
    parser.add_argument('old_path', type=str, help='源文件路径')
    parser.add_argument('new_path', type=str, help='目标文件路径')
    args = parser.parse_args()
    main(old_path=args.old_path, new_path=args.new_path)
