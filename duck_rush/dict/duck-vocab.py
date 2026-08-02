# -*- coding: utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2026/08/01
# @modified 2026/08/01
'''
命令行生词本 (duck-vocab)

把需要记忆的单词 / 词条集中管理, 支持释义、例句、笔记与标签, 并可标记掌握状态、
进行自测复习。数据保存在用户级数据目录 (~/.duck-rush/data/duck-vocab/vocab.jsonl),
不污染仓库。

用法:
    duck-vocab add <word> [-m 释义] [-e 例句] [-n 笔记] [-t 标签1,标签2]
    duck-vocab list [-t 标签] [-s 关键词] [--unmastered]
    duck-vocab show <id>
    duck-vocab update <id> [-w 单词] [-m 释义] [-e 例句] [-n 笔记] [-t 标签]
    duck-vocab remove <id> [-y]           # 按 ID 删除 (别名: delete)
    duck-vocab master <id> [--off]        # 标记/取消掌握
    duck-vocab quiz [--count N] [-t 标签]  # 自测复习(仅未掌握词条)

示例:
    duck-vocab add hello -m 你好 -e "say hello" -t greeting
    duck-vocab update 3 -m 新的释义 -t 新标签    # 仅更新给定字段
    duck-vocab remove 3                         # 删除前确认
    duck-vocab remove 3 -y                      # 跳过确认直接删除
    duck-vocab list --unmastered
    duck-vocab quiz --count 10
    duck-vocab master 3

说明:
    - 各子命令加 -h 可查看详细参数, 如: duck-vocab add -h
    - -h/--help 仅打印帮助并以 0 退出, 不读写数据、不创建文件
    - update 仅修改给出的字段, 未给出的字段保持原值
    - remove/delete 为破坏性操作, 默认需交互确认; 加 -y/--yes 可跳过确认
'''
import os
import sys
import time
import random
import argparse
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

try:
    from duck_utils.os_util import get_command_data_dir
    from duck_utils.jsonl_util import JsonlStore
except ImportError:
    sys.stderr.write("无法导入 duck_utils 模块, 请先执行 `python install.py` 安装后重试。\n")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------
@dataclass
class VocabEntry:
    """一条生词记录"""
    word: str
    meaning: str = ""
    example: str = ""
    note: str = ""
    tags: List[str] = field(default_factory=list)
    mastered: bool = False
    review_count: int = 0
    created_time: float = 0.0
    id: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "word": self.word,
            "meaning": self.meaning,
            "example": self.example,
            "note": self.note,
            "tags": list(self.tags),
            "mastered": self.mastered,
            "review_count": self.review_count,
            "created_time": self.created_time,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "VocabEntry":
        raw_tags = d.get("tags") or []
        if isinstance(raw_tags, str):
            # 兼容旧格式: 标签以逗号拼接成字符串
            raw_tags = [t for t in raw_tags.split(",") if t]
        return VocabEntry(
            id=d.get("id", 0),
            word=d.get("word", ""),
            meaning=d.get("meaning", ""),
            example=d.get("example", ""),
            note=d.get("note", ""),
            tags=list(raw_tags),
            mastered=bool(d.get("mastered", False)),
            review_count=d.get("review_count", 0),
            created_time=d.get("created_time", 0.0),
        )


# ---------------------------------------------------------------------------
# DAO: JSONL 持久化层
# ---------------------------------------------------------------------------
class VocabDao:
    """生词数据的 JSONL 持久化层 (DAO)"""

    def __init__(self, path: Optional[str] = None) -> None:
        if path is None:
            path = os.path.join(get_command_data_dir("duck-vocab"), "vocab.jsonl")
        self.path = path
        self.store = JsonlStore(path)

    def _read_all(self) -> List[VocabEntry]:
        """读取全部记录, 跳过空行与损坏行"""
        result: List[VocabEntry] = []
        for rec in self.store.read_all():
            try:
                result.append(VocabEntry.from_dict(rec))
            except (AttributeError, TypeError):
                continue
        return result

    def _write_all(self, items: List[VocabEntry]) -> None:
        """整体重写文件 (原子替换, 避免半写损坏)"""
        self.store.write_all([it.to_dict() for it in items], atomic=True)

    def add(self, word: str, meaning: str, example: str, note: str,
            tags: Optional[List[str]] = None) -> VocabEntry:
        items = self._read_all()
        new_id = max([it.id for it in items], default=0) + 1
        entry = VocabEntry(
            id=new_id,
            word=word,
            meaning=meaning,
            example=example,
            note=note,
            tags=tags or [],
            mastered=False,
            review_count=0,
            created_time=time.time(),
        )
        items.append(entry)
        self._write_all(items)
        return entry

    def list_all(self) -> List[VocabEntry]:
        return sorted(self._read_all(), key=lambda x: x.id)

    def get_by_id(self, rid: int) -> Optional[VocabEntry]:
        for e in self._read_all():
            if e.id == rid:
                return e
        return None

    def search(self, query: str, tag: Optional[str],
               unmastered_only: bool) -> List[VocabEntry]:
        items = self._read_all()
        if unmastered_only:
            items = [e for e in items if not e.mastered]
        if tag:
            items = [e for e in items if tag in e.tags]
        if query:
            q = query.lower()
            def _match(e: VocabEntry) -> bool:
                blob = (e.word + e.meaning + e.example + e.note + ",".join(e.tags)).lower()
                return q in blob
            items = [e for e in items if _match(e)]
        items.sort(key=lambda x: x.id)
        return items

    def remove(self, rid: int) -> bool:
        items = self._read_all()
        new_items = [e for e in items if e.id != rid]
        if len(new_items) == len(items):
            return False
        self._write_all(new_items)
        return True

    def update(self, rid: int, **fields: Any) -> Optional[VocabEntry]:
        """按 ID 更新给定字段 (仅修改传入的键), 返回更新后的记录或 None。"""
        items = self._read_all()
        for e in items:
            if e.id == rid:
                for key in ("word", "meaning", "example", "note", "tags", "mastered"):
                    if key in fields and fields[key] is not None:
                        setattr(e, key, fields[key])
                self._write_all(items)
                return e
        return None

    def set_mastered(self, rid: int, value: bool) -> bool:
        items = self._read_all()
        for e in items:
            if e.id == rid:
                e.mastered = value
                if value:
                    # 掌握后清空复习计数, 重新学习时可重新累计
                    e.review_count = 0
                self._write_all(items)
                return True
        return False

    def increment_review(self, rid: int) -> bool:
        items = self._read_all()
        for e in items:
            if e.id == rid:
                e.review_count += 1
                self._write_all(items)
                return True
        return False


# 延迟初始化, 避免在 -h 等仅打印帮助的场景下创建数据目录 (无副作用)
_dao: Optional[VocabDao] = None


def get_dao() -> VocabDao:
    global _dao
    if _dao is None:
        _dao = VocabDao()
    return _dao


# ---------------------------------------------------------------------------
# 展示
# ---------------------------------------------------------------------------
def _print_entry_line(e: VocabEntry) -> None:
    mark = "✓" if e.mastered else " "
    line = "%s %-4d %s" % (mark, e.id, e.word)
    if e.meaning:
        line += "  → " + e.meaning
    if e.tags:
        line += "  [#%s]" % ",".join(e.tags)
    print(line)


# ---------------------------------------------------------------------------
# 子命令处理
# ---------------------------------------------------------------------------
def cmd_add(args: argparse.Namespace) -> None:
    word = (args.word or "").strip()
    if not word:
        sys.stderr.write("单词不能为空\n")
        sys.exit(1)
    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    entry = get_dao().add(
        word=word,
        meaning=args.meaning or "",
        example=args.example or "",
        note=args.note or "",
        tags=tags,
    )
    print("已添加生词 #%d: %s" % (entry.id, entry.word))
    if entry.meaning:
        print("  释义: %s" % entry.meaning)
    if entry.example:
        print("  例句: %s" % entry.example)
    if entry.note:
        print("  笔记: %s" % entry.note)
    if entry.tags:
        print("  标签: %s" % ", ".join(entry.tags))


def cmd_list(args: argparse.Namespace) -> None:
    items = get_dao().search(
        query=args.search or "",
        tag=args.tag,
        unmastered_only=args.unmastered,
    )
    if not items:
        print("生词本为空" if not (args.search or args.tag or args.unmastered)
              else "没有匹配的生词")
        return
    for e in items:
        _print_entry_line(e)
    print("\n共 %d 条" % len(items))


def cmd_show(args: argparse.Namespace) -> None:
    e = get_dao().get_by_id(args.id)
    if e is None:
        print("未找到 ID=%d 的生词" % args.id)
        return
    print("ID:   %d" % e.id)
    print("单词: %s" % e.word)
    print("释义: %s" % (e.meaning or "(空)"))
    if e.example:
        print("例句: %s" % e.example)
    if e.note:
        print("笔记: %s" % e.note)
    if e.tags:
        print("标签: %s" % ", ".join(e.tags))
    print("状态: %s" % ("已掌握" if e.mastered else "学习中"))
    if e.review_count:
        print("复习次数: %d" % e.review_count)


def cmd_remove(args: argparse.Namespace) -> None:
    dao = get_dao()
    e = dao.get_by_id(args.id)
    if e is None:
        print("未找到 #%d" % args.id)
        return
    if not args.yes:
        # 破坏性操作, 默认交互确认; 非交互(stdin 非终端)时不读取输入,
        # 直接取消, 避免管道场景下 input() 阻塞
        if not sys.stdin.isatty():
            print("非交互环境未指定 -y, 已取消删除 (用 -y 可跳过确认)")
            return
        try:
            ans = input("确定删除 #%d (%s)? [y/N] " % (e.id, e.word)).strip().lower()
        except EOFError:
            ans = ""
        if ans != "y":
            print("已取消删除")
            return
    if dao.remove(args.id):
        print("已删除 #%d: %s" % (args.id, e.word))
    else:
        print("未找到 #%d" % args.id)


def cmd_update(args: argparse.Namespace) -> None:
    fields: Dict[str, Any] = {}
    if args.word is not None:
        w = args.word.strip()
        if not w:
            sys.stderr.write("单词不能为空\n")
            sys.exit(1)
        fields["word"] = w
    if args.meaning is not None:
        fields["meaning"] = args.meaning
    if args.example is not None:
        fields["example"] = args.example
    if args.note is not None:
        fields["note"] = args.note
    if args.tags is not None:
        fields["tags"] = [t.strip() for t in args.tags.split(",") if t.strip()]
    if not fields:
        print("未提供任何要更新的字段 (可用 -w/-m/-e/-n/-t)")
        return
    e = get_dao().update(args.id, **fields)
    if e is None:
        print("未找到 #%d" % args.id)
        return
    print("已更新 #%d: %s" % (e.id, e.word))
    if e.meaning:
        print("  释义: %s" % e.meaning)
    if e.example:
        print("  例句: %s" % e.example)
    if e.note:
        print("  笔记: %s" % e.note)
    if e.tags:
        print("  标签: %s" % ", ".join(e.tags))


def cmd_master(args: argparse.Namespace) -> None:
    if get_dao().set_mastered(args.id, not args.off):
        print("%s #%d" % ("已标记为掌握" if not args.off else "已取消掌握", args.id))
    else:
        print("未找到 #%d" % args.id)


def cmd_quiz(args: argparse.Namespace) -> None:
    items = get_dao().search(query="", tag=args.tag, unmastered_only=True)
    if not items:
        print("没有待复习的生词 (全部已掌握或为空)。")
        return
    random.shuffle(items)
    if args.count and args.count > 0:
        items = items[:args.count]

    correct = 0
    total = len(items)
    print("开始复习, 共 %d 个生词 (输入 n 表示未记住, 其它键表示已记住)\n" % total)
    for e in items:
        print("单词: %s" % e.word)
        try:
            input("按回车查看释义 ...")
        except EOFError:
            # 非交互场景(管道输入)直接展示, 避免卡住
            print("")
        print("释义: %s" % (e.meaning or "(无)"))
        if e.example:
            print("例句: %s" % e.example)
        try:
            ans = input("是否记住了? (y/n) [n]: ").strip().lower()
        except EOFError:
            ans = ""
        if ans == "y":
            correct += 1
            get_dao().set_mastered(e.id, True)
        else:
            get_dao().increment_review(e.id)
    print("\n本次复习 %d 个, 记住 %d 个。" % (total, correct))


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="命令行生词本 (单词/词条记忆与管理)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("示例:\n"
                "  duck-vocab add hello -m 你好 -e \"say hello\" -t greeting\n"
                "  duck-vocab list --unmastered\n"
                "  duck-vocab list -s hello          # 按关键词搜索\n"
                "  duck-vocab show 3\n"
                "  duck-vocab update 3 -m 新释义 -t 新标签   # 更新生词\n"
                "  duck-vocab remove 3 -y            # 按 ID 删除\n"
                "  duck-vocab master 3               # 标记为已掌握\n"
                "  duck-vocab quiz --count 10        # 自测复习 10 个未掌握词条\n"
                "各子命令加 -h 可查看详细参数, 如: duck-vocab add -h"))
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser(
        "add", help="添加生词",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("添加一条生词。\n"
                     "示例:\n"
                     "  duck-vocab add hello -m 你好 -e \"say hello\" -t greeting\n"
                     "  duck-vocab add deferred -m 推迟的 -n 常与 defer 混淆"))
    p_add.add_argument("word", help="单词/词条 (如 hello)")
    p_add.add_argument("-m", "--meaning", default="", help="释义")
    p_add.add_argument("-e", "--example", default="", help="例句")
    p_add.add_argument("-n", "--note", default="", help="笔记/备注")
    p_add.add_argument("-t", "--tags", default="", help="标签, 多个用逗号分隔 (如 greeting,verb)")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser(
        "list", help="列出生词",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("列出生词。\n"
                     "示例:\n"
                     "  duck-vocab list                 # 列出全部\n"
                     "  duck-vocab list --unmastered    # 仅未掌握\n"
                     "  duck-vocab list -t greeting     # 按标签筛选\n"
                     "  duck-vocab list -s hello        # 按关键词搜索"))
    p_list.add_argument("-t", "--tag", default=None, help="按标签筛选")
    p_list.add_argument("-s", "--search", default="", help="关键词搜索 (匹配单词/释义/例句/笔记/标签)")
    p_list.add_argument("--unmastered", action="store_true", help="仅显示未掌握的词条")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="查看生词详情")
    p_show.add_argument("id", type=int, help="生词 ID (可用 list 查看)")
    p_show.set_defaults(func=cmd_show)

    p_rm = sub.add_parser(
        "remove", help="按 ID 删除生词",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("按 ID 删除一条生词 (破坏性操作, 默认需确认)。\n"
                     "别名 delete 等价。\n"
                     "示例:\n"
                     "  duck-vocab remove 3        # 删除前交互确认\n"
                     "  duck-vocab remove 3 -y     # 跳过确认直接删除\n"
                     "  duck-vocab delete 3        # 等价别名"))
    p_rm.add_argument("id", type=int, help="生词 ID (可用 list 查看)")
    p_rm.add_argument("-y", "--yes", action="store_true", help="跳过确认直接删除")
    p_rm.set_defaults(func=cmd_remove)

    p_del = sub.add_parser("delete", help="按 ID 删除生词 (remove 的别名)")
    p_del.add_argument("id", type=int, help="生词 ID (可用 list 查看)")
    p_del.add_argument("-y", "--yes", action="store_true", help="跳过确认直接删除")
    p_del.set_defaults(func=cmd_remove)

    p_update = sub.add_parser(
        "update", help="按 ID 更新生词",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("按 ID 更新生词的字段, 仅修改给出的字段, 其余保持原值。\n"
                     "示例:\n"
                     "  duck-vocab update 3 -m 新释义 -t 新标签\n"
                     "  duck-vocab update 3 -w newword -e \"new example\""))
    p_update.add_argument("id", type=int, help="生词 ID (可用 list 查看)")
    p_update.add_argument("-w", "--word", default=None, help="新单词/词条")
    p_update.add_argument("-m", "--meaning", default=None, help="新释义")
    p_update.add_argument("-e", "--example", default=None, help="新例句")
    p_update.add_argument("-n", "--note", default=None, help="新笔记/备注")
    p_update.add_argument("-t", "--tags", default=None,
                           help="新标签, 多个用逗号分隔 (如 greeting,verb)")
    p_update.set_defaults(func=cmd_update)

    p_master = sub.add_parser(
        "master", help="标记/取消掌握",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("标记词条为已掌握 (或取消)。\n"
                     "示例:\n"
                     "  duck-vocab master 3         # 标记为已掌握\n"
                     "  duck-vocab master 3 --off   # 取消掌握"))
    p_master.add_argument("id", type=int, help="生词 ID (可用 list 查看)")
    p_master.add_argument("--off", action="store_true", help="取消掌握 (而非标记掌握)")
    p_master.set_defaults(func=cmd_master)

    p_quiz = sub.add_parser(
        "quiz", help="自测复习",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("自测复习未掌握的词条: 显示单词, 按回车看释义, 再判断是否记住。\n"
                     "记住则标记掌握, 未记住则累计复习次数。\n"
                     "示例:\n"
                     "  duck-vocab quiz             # 复习全部未掌握\n"
                     "  duck-vocab quiz --count 10  # 仅复习 10 个\n"
                     "  duck-vocab quiz -t greeting # 仅复习该标签下未掌握"))
    p_quiz.add_argument("--count", type=int, default=0, help="复习数量 (默认 0 = 全部未掌握)")
    p_quiz.add_argument("-t", "--tag", default=None, help="仅复习该标签下的未掌握词条")
    p_quiz.set_defaults(func=cmd_quiz)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
