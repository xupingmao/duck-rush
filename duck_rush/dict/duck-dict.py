# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2026/07/15
# @modified 2026/07/15
'''
命令行字典工具 (duck-dict)

快速查找与编辑键值字典, 每个 key 对应一个字符串列表, 支持 update / append 两种模式。

用法:
    python duck-dict.py get <key>               精确查找某个 key (也可直接 duck-dict <key>)
    python duck-dict.py search <pattern>        按 key 模糊/正则搜索
    python duck-dict.py update <key> <v>...     覆盖写入(update 模式): 用给定值替换该 key
    python duck-dict.py set <key> <v>...        update 的别名: 覆盖写入
    python duck-dict.py append <key> <v>...     追加写入(append 模式): 在列表末尾添加值
    python duck-dict.py list                    列出所有 key
    python duck-dict.py remove <key>            删除某个 key
    python duck-dict.py pop <key> [index]       删除某 key 下第 index 条(默认最后一条)
    python duck-dict.py edit <key>              用 $EDITOR 打开编辑该 key 的值

说明:
    - 数据默认存放在 data/dict/dict.jsonl(JSONL, 紧凑无缩进), 可用 -f/--file 指定其它文件
    - update 与 append 均接受多个值参数, 每个参数作为列表中的一项
'''
import os
import sys
import re
import json
import argparse
import subprocess
from typing import Dict, List, Optional, Any

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(REPO_ROOT, "data")
DEFAULT_DICT_PATH = os.path.join(DATA_DIR, "dict", "dict.jsonl")


# ---------------------------------------------------------------------------
# 字典存储层 (DAO)
# ---------------------------------------------------------------------------
class DictStore:
    """键值字典的 JSONL 持久化层, 每个 key 对应一个字符串列表"""

    def __init__(self, path: str = DEFAULT_DICT_PATH) -> None:
        self.path = path

    def _ensure_dir(self) -> None:
        d = os.path.dirname(self.path)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)

    def load(self) -> Dict[str, List[str]]:
        """逐行读取 JSONL, 规整为 {key: [str, ...]} 形式, 跳过空行与损坏行"""
        if not os.path.exists(self.path):
            return {}
        result: Dict[str, List[str]] = {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    k = obj.get("key")
                    v = obj.get("values", [])
                    if k is None:
                        continue
                    if isinstance(v, list):
                        result[k] = [str(x) for x in v]
                    else:
                        result[k] = [str(v)]
        except OSError:
            return {}
        return result

    def save(self, data: Dict[str, List[str]]) -> None:
        """整体写回为紧凑 JSONL(每行一条, 无缩进, 先写临时文件再原子替换)"""
        self._ensure_dir()
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for k, v in data.items():
                entry = {"key": k, "values": v}
                f.write(json.dumps(entry, ensure_ascii=False,
                                   separators=(",", ":")) + "\n")
        os.replace(tmp, self.path)

    def get(self, key: str) -> Optional[List[str]]:
        return self.load().get(key)

    def set_replace(self, key: str, values: List[str]) -> int:
        """update 模式: 用 values 覆盖该 key"""
        data = self.load()
        data[key] = list(values)
        self.save(data)
        return len(data[key])

    def append(self, key: str, values: List[str]) -> int:
        """append 模式: 在 key 的列表末尾追加 values"""
        data = self.load()
        data.setdefault(key, []).extend(values)
        self.save(data)
        return len(data[key])

    def remove(self, key: str) -> bool:
        data = self.load()
        if key in data:
            data.pop(key)
            self.save(data)
            return True
        return False

    def remove_item(self, key: str, index: int) -> bool:
        data = self.load()
        items = data.get(key)
        if not items or index < 0 or index >= len(items):
            return False
        items.pop(index)
        self.save(data)
        return True

    def search(self, pattern: str) -> List[Dict[str, Any]]:
        """按 key 搜索, 优先正则, 失败则退化为子串匹配"""
        data = self.load()
        try:
            rx = re.compile(pattern)
            match = lambda k: rx.search(k) is not None
        except re.error:
            match = lambda k: pattern in k
        return [{"key": k, "values": v} for k, v in data.items() if match(k)]

    def keys(self) -> List[str]:
        return sorted(self.load().keys())


# ---------------------------------------------------------------------------
# CLI 命令
# ---------------------------------------------------------------------------
def _print_values(key: str, values: List[str]) -> None:
    if not values:
        print("[%s] (空)" % key)
        return
    print("[%s]" % key)
    for i, v in enumerate(values, 1):
        print("  %d. %s" % (i, v))


def cmd_get(args: argparse.Namespace) -> None:
    store: DictStore = args.store
    values = store.get(args.key)
    if values is None:
        print("未找到 key: %s" % args.key)
        print("(可用 `duck-dict search %s` 尝试模糊搜索)" % args.key)
        return
    _print_values(args.key, values)


def cmd_search(args: argparse.Namespace) -> None:
    store: DictStore = args.store
    hits = store.search(args.pattern)
    if not hits:
        print("没有匹配 key: %s" % args.pattern)
        return
    for hit in hits:
        _print_values(hit["key"], hit["values"])
        print()


def cmd_update(args: argparse.Namespace) -> None:
    store: DictStore = args.store
    n = store.set_replace(args.key, args.values)
    print("已(update)写入 %s, 共 %d 项" % (args.key, n))


def cmd_append(args: argparse.Namespace) -> None:
    store: DictStore = args.store
    n = store.append(args.key, args.values)
    print("已(append)追加到 %s, 现共 %d 项" % (args.key, n))


def cmd_list(args: argparse.Namespace) -> None:
    store: DictStore = args.store
    keys = store.keys()
    if not keys:
        print("字典为空")
        return
    print("共 %d 个 key:" % len(keys))
    for k in keys:
        print("  %s" % k)


def cmd_remove(args: argparse.Namespace) -> None:
    store: DictStore = args.store
    if store.remove(args.key):
        print("已删除 key: %s" % args.key)
    else:
        print("未找到 key: %s" % args.key)


def cmd_pop(args: argparse.Namespace) -> None:
    store: DictStore = args.store
    values = store.get(args.key)
    if values is None:
        print("未找到 key: %s" % args.key)
        return
    index = args.index if args.index is not None else len(values) - 1
    if store.remove_item(args.key, index):
        print("已删除 %s 的第 %d 条" % (args.key, index + 1))
    else:
        print("索引越界: %s 共 %d 条" % (args.key, len(values)))


def cmd_edit(args: argparse.Namespace) -> None:
    """用 $EDITOR 打开编辑该 key 的值(每行一条)"""
    store: DictStore = args.store
    values = store.get(args.key)
    if values is None:
        values = []
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor:
        print("未设置 $EDITOR, 无法打开编辑器。可用 update/append 编辑。")
        print("当前值:")
        _print_values(args.key, values)
        return
    tmp = store.path + ".%s.edit.tmp" % args.key
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(values) + ("\n" if values else ""))
    try:
        subprocess.call([editor, tmp])
        with open(tmp, "r", encoding="utf-8") as f:
            new_values = [line.rstrip("\n") for line in f.read().splitlines()]
        store.set_replace(args.key, new_values)
        print("已更新 %s, 共 %d 项" % (args.key, len(new_values)))
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 解析 & 入口
# ---------------------------------------------------------------------------
SUBCOMMANDS = {"get", "search", "update", "set", "append", "list", "remove", "pop", "edit"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="命令行字典工具")
    parser.add_argument("-f", "--file", default=DEFAULT_DICT_PATH,
                        help="字典文件路径(默认 %s)" % DEFAULT_DICT_PATH)

    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("get", help="精确查找 key")
    p.add_argument("key")
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("search", help="按 key 模糊/正则搜索")
    p.add_argument("pattern")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("update", help="覆盖写入(update 模式)")
    p.add_argument("key")
    p.add_argument("values", nargs="+", help="一个或多个值, 每个作为列表一项")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("set", help="update 的别名: 覆盖写入")
    p.add_argument("key")
    p.add_argument("values", nargs="+", help="一个或多个值, 每个作为列表一项")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("append", help="追加写入(append 模式)")
    p.add_argument("key")
    p.add_argument("values", nargs="+", help="一个或多个值, 每个作为列表一项")
    p.set_defaults(func=cmd_append)

    p = sub.add_parser("list", help="列出所有 key")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("remove", help="删除 key")
    p.add_argument("key")
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("pop", help="删除 key 下某一条")
    p.add_argument("key")
    p.add_argument("index", nargs="?", type=int, default=None,
                   help="条目序号(从1开始, 默认最后一条)")
    p.set_defaults(func=cmd_pop)

    p = sub.add_parser("edit", help="用编辑器编辑 key")
    p.add_argument("key")
    p.set_defaults(func=cmd_edit)

    return parser


def main() -> None:
    argv = sys.argv[1:]
    # 快速查找: 第一个参数既不是已知子命令, 也不是选项(-开头)时, 当作 key 直接 get
    if (argv and not argv[0].startswith("-")
            and argv[0] not in SUBCOMMANDS and argv[0] not in ("-h", "--help")):
        key = " ".join(argv)
        store = DictStore(DEFAULT_DICT_PATH)
        cmd_get_type = argparse.Namespace(key=key, store=store)
        cmd_get(cmd_get_type)
        return

    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        return
    args.store = DictStore(args.file)
    args.func(args)


if __name__ == "__main__":
    main()
