# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2023/02/05 14:30:00
# @modified 2023/02/05 14:30:00

import re
import argparse
from typing import Optional

try:
    from duck_leveldb import LevelDB
except ImportError:
    print("请先安装 duck_leveldb: pip install duck_leveldb")
    raise


def print_help() -> None:
    print("""
.quit       退出 shell
.q          退出 shell
.exit       退出 shell
get <key>   获取指定 key 的值
put <k> <v> 设置 key-value
del <key>   删除指定 key
scan [--key-regex K] [--value-regex V] [--offset N] [--limit N]  扫描
count [--key-regex K] [--value-regex V] 计数
.help       显示帮助信息
""")


def parse_kv_args(line: str) -> tuple:
    parts = line.strip().split(maxsplit=1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0] if parts else None, None


class LeveldbShell:
    def __init__(self, db_path: str, create: bool = False) -> None:
        self.db_path = db_path
        self.db = LevelDB(db_path, create)
        self._init_cmd_map()

    def close(self) -> None:
        if self.db:
            self.db.close()
            self.db = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def cmd_get(self, args: str) -> None:
        val = self.db.get(args.strip().encode())
        if val is None:
            print("(not found)")
        else:
            print(val.decode())

    def cmd_put(self, key: str, value: str) -> None:
        self.db.put(key.encode(), value.encode())
        print("OK")

    def cmd_delete(self, args: str) -> None:
        self.db.delete(args.strip().encode())
        print("OK")

    def _compile_regex(self, pattern: Optional[str]) -> Optional[re.Pattern]:
        if not pattern:
            return None
        try:
            return re.compile(pattern)
        except re.error as e:
            print("正则表达式错误: %s" % e)
            return None

    def _scan_all(self,
                  key_regex: Optional[str] = None,
                  value_regex: Optional[str] = None) -> list:
        key_pattern = self._compile_regex(key_regex)
        value_pattern = self._compile_regex(value_regex)
        results = []
        with self.db.iterator() as it:
            for k, v in it:
                k = k.decode()
                v = v.decode()
                if key_pattern and not key_pattern.search(k):
                    continue
                if value_pattern and not value_pattern.search(v):
                    continue
                results.append((k, v))
        return results

    def cmd_scan(self,
                 key_regex: Optional[str] = None,
                 value_regex: Optional[str] = None,
                 offset: int = 0,
                 limit: int = 20) -> None:
        all_rows = self._scan_all(key_regex, value_regex)
        total = len(all_rows)
        page = all_rows[offset:offset + limit]
        for k, v in page:
            print("%s = %s" % (k, v))
        print("\n(%d rows, offset=%d, limit=%d, total=%d)" % (len(page), offset, limit, total))

    def cmd_count(self,
                  key_regex: Optional[str] = None,
                  value_regex: Optional[str] = None) -> None:
        all_rows = self._scan_all(key_regex, value_regex)
        print(len(all_rows))

    def _exec_put(self, args: str) -> None:
        k, v = parse_kv_args(args)
        if k is None or v is None:
            print("用法: put <key> <value>")
            return
        self.cmd_put(k, v)

    _DOT_CMDS = {"quit", "q", "exit"}

    def _init_cmd_map(self) -> None:
        self._cmd_map = {
            "get": self.cmd_get,
            "put": self._exec_put,
            "del": self.cmd_delete,
            "scan": self.cmd_scan_inline,
            "count": self.cmd_count_inline,
        }

    def exec_dot_command(self, line: str) -> bool:
        parts = line[1:].strip().split(maxsplit=2)
        if not parts:
            return True
        cmd = parts[0].lower()
        if cmd in self._DOT_CMDS:
            return False
        if cmd == "help":
            print_help()
            return True
        self.exec_line(line[1:].strip())
        return True

    def exec_line(self, line: str) -> None:
        parts = line.strip().split(maxsplit=1)
        if not parts:
            return
        cmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        handler = self._cmd_map.get(cmd)
        if handler:
            handler(rest)
        else:
            print("未知命令: %s，输入 .help 查看帮助" % cmd)

    def cmd_scan_inline(self, args_str: str) -> None:
        parser = argparse.ArgumentParser(prog="scan", add_help=False)
        parser.add_argument("--key-regex", default=None)
        parser.add_argument("--value-regex", default=None)
        parser.add_argument("--offset", type=int, default=0)
        parser.add_argument("--limit", type=int, default=20)
        try:
            ns = parser.parse_args(args_str.split())
        except SystemExit:
            return
        self.cmd_scan(ns.key_regex, ns.value_regex, ns.offset, ns.limit)

    def cmd_count_inline(self, args_str: str) -> None:
        parser = argparse.ArgumentParser(prog="count", add_help=False)
        parser.add_argument("--key-regex", default=None)
        parser.add_argument("--value-regex", default=None)
        try:
            ns = parser.parse_args(args_str.split())
        except SystemExit:
            return
        self.cmd_count(ns.key_regex, ns.value_regex)

    def run_interactive(self) -> None:
        print_help()
        while True:
            try:
                line = input("leveldb> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line.startswith("."):
                if not self.exec_dot_command(line):
                    break
            else:
                self.exec_line(line)

    def run_one_shot(self, cmd: str, args_str: str = "") -> None:
        handler = self._cmd_map.get(cmd)
        if handler:
            handler(args_str)


def main() -> None:
    parser = argparse.ArgumentParser(description="LevelDB 命令行工具")
    parser.add_argument("database", help="数据库目录路径")
    parser.add_argument("command", nargs="?", default=None,
                        help="命令: get/put/del/scan/count（不指定则进入交互模式）")
    parser.add_argument("args", nargs=argparse.REMAINDER,
                        help="命令参数")
    parser.add_argument("-c", "--create", action="store_true",
                        help="如果数据库目录不存在，自动创建")
    args = parser.parse_args()

    with LeveldbShell(args.database, create=args.create) as shell:
        if args.command:
            shell.run_one_shot(args.command, " ".join(args.args))
        else:
            shell.run_interactive()


if __name__ == "__main__":
    main()
