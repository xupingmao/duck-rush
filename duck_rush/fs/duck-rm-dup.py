# -*- coding:utf-8 -*-
import os
import sys
import hashlib
from typing import Dict, List

CHUNK_SIZE = 8192

ALGORITHMS = sorted(hashlib.algorithms_available)

class RmDupConfig:
    debug = False

def calc_hash(fpath: str, algorithm: str = "sha256") -> str:
    m = hashlib.new(algorithm)
    with open(fpath, "rb") as fh:
        while True:
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                break
            m.update(chunk)
    return m.hexdigest()


def collect_files(root_dir: str, recursive: bool = False) -> List[str]:
    files: List[str] = []
    if recursive:
        for dirpath, _, filenames in os.walk(root_dir):
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                if os.path.isfile(fpath):
                    files.append(fpath)
    else:
        for name in os.listdir(root_dir):
            fpath = os.path.join(root_dir, name)
            if os.path.isfile(fpath):
                files.append(fpath)
    return files


def prompt_confirm(files: List[str], hash_val: str, algorithm: str) -> bool:
    print("=" * 60)
    print(f"发现重复文件 ({algorithm}): {hash_val}")
    print(f"  保留: {files[0]}")
    for f in files[1:]:
        print(f"  删除: {f}")
    ans = input("\n确认删除以上文件? [y/N] ").strip().lower()
    return ans in ("y", "yes")


def main(
    directory: str = ".",
    algorithm: str = "sha256",
    recursive: bool = False,
    dry_run: bool = False,
):
    if not os.path.isdir(directory):
        print(f"错误: 目录不存在 - {directory}", file=sys.stderr)
        sys.exit(1)

    if algorithm not in ALGORITHMS:
        print(f"不支持的哈希算法: {algorithm}", file=sys.stderr)
        print(f"可用算法: {', '.join(ALGORITHMS)}", file=sys.stderr)
        sys.exit(1)

    files = collect_files(directory, recursive=recursive)
    if not files:
        print("未找到文件")
        return

    print(f"正在计算 {len(files)} 个文件的哈希值 ({algorithm})...")
    hash_map: Dict[str, List[str]] = {}
    errors = 0
    for fpath in files:
        try:
            h = calc_hash(fpath, algorithm=algorithm)
            if RmDupConfig:
                print(f"DEBUG: {h} --> {fpath}")
            hash_map.setdefault(h, []).append(fpath)
        except (OSError, PermissionError) as e:
            print(f"跳过 {fpath}: {e}", file=sys.stderr)
            errors += 1

    dup_groups = [(h, paths) for h, paths in hash_map.items() if len(paths) > 1]
    if not dup_groups:
        print("未发现重复文件")
        return

    print(f"\n发现 {len(dup_groups)} 组重复文件, 共 {sum(len(g) - 1 for _, g in dup_groups)} 个冗余文件\n")

    total_deleted = 0
    for hash_val, paths in dup_groups:
        if not prompt_confirm(paths, hash_val, algorithm):
            print("  已跳过\n")
            continue
        for fpath in paths[1:]:
            if dry_run:
                print(f"  [模拟] 删除: {fpath}")
            else:
                try:
                    os.remove(fpath)
                    print(f"  已删除: {fpath}")
                    total_deleted += 1
                except OSError as e:
                    print(f"  删除失败: {fpath} - {e}", file=sys.stderr)
        print()

    if dry_run:
        print(f"模拟运行结束, 共 {total_deleted} 个文件将被删除")
    else:
        print(f"完成, 共删除 {total_deleted} 个重复文件")

    if errors:
        print(f"警告: {errors} 个文件因错误被跳过", file=sys.stderr)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="清理重复文件，基于哈希值保留一份，删除其余")
    parser.add_argument("directory", nargs="?", default=".", help="要扫描的目录（默认当前目录）")
    parser.add_argument("--algo", default="sha256", choices=ALGORITHMS,
                        help="哈希算法（默认 sha256）")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="递归子目录")
    parser.add_argument("--dry-run", action="store_true",
                        help="模拟运行，不实际删除")
    parser.add_argument("--debug", action="store_true", help="打印调试信息")
    args = parser.parse_args()
    
    RmDupConfig.debug = args.debug
    
    main(
        directory=args.directory,
        algorithm=args.algo,
        recursive=args.recursive,
        dry_run=args.dry_run,
    )
