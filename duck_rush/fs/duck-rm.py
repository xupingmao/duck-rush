import argparse
import os
import shutil
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="删除文件或目录")
    parser.add_argument("paths", nargs="+", help="要删除的文件或目录")
    parser.add_argument("-r", "-R", "--recursive", action="store_true", help="递归删除目录")
    parser.add_argument("-f", "--force", action="store_true", help="强制删除，忽略不存在的文件")
    parser.add_argument("-i", "--interactive", action="store_true", help="删除前询问确认")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细信息")
    args = parser.parse_args()

    removed: list[str] = []

    for path in args.paths:
        if not os.path.exists(path):
            if not args.force:
                print(f"无法删除 '{path}': No such file or directory")
            continue

        if os.path.isdir(path):
            if not args.recursive:
                print(f"无法删除 '{path}': 是一个目录")
                continue

            if args.interactive:
                response = input(f"是否删除目录 '{path}' 及其内容? [y/n] ")
                if response.lower() not in ("y", "yes"):
                    print("跳过")
                    continue

            try:
                shutil.rmtree(path)
                removed.append(path)
                if args.verbose:
                    print(f"已删除目录: {path}")
            except Exception as e:
                print(f"删除目录 '{path}' 失败: {e}")
        else:
            if args.interactive:
                response = input(f"是否删除文件 '{path}'? [y/n] ")
                if response.lower() not in ("y", "yes"):
                    print("跳过")
                    continue

            try:
                os.remove(path)
                removed.append(path)
                if args.verbose:
                    print(f"已删除: {path}")
            except Exception as e:
                print(f"删除文件 '{path}' 失败: {e}")

    if not removed:
        sys.exit(1)


if __name__ == "__main__":
    main()
