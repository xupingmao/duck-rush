# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2026/07/19
# @modified 2026/07/19
'''
命令行日历工具 (duck-calendar) —— 展示与管理日程

用法:
    python duck-calendar.py add <日期> <标题> [--time 时:分] [--desc 说明] [--location 地点]
    python duck-calendar.py list [--date 日期 | --month 年月 | --upcoming [N] | --all]
    python duck-calendar.py show [YYYY-MM | YYYY-MM-DD]       查看月历(标注有日程的日期)
    python duck-calendar.py today                                    查看今天日程
    python duck-calendar.py update <id> [--date ..] [--time ..] [--title ..] [--desc ..] [--location ..]
    python duck-calendar.py delete <id>                            删除日程

日期格式:
    today / tomorrow
    YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD
    MM-DD / MM/DD            (取当前年)

数据:
    所有日程以 SQLite 存储于 data/calendar/calendar.db
    数据对象使用 CalendarEvent 类, 持久化封装在 CalendarDao 中(基于 duck_utils.sqlite_util)
'''
import os
import re
import sys
import time
import argparse
import calendar
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

try:
    from duck_utils.sqlite_util import SqliteTableManager
except ImportError:
    sys.stderr.write("无法导入 duck_utils 模块, 请先执行 `python install.py` 安装后重试。\n")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 路径 & 常量
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(REPO_ROOT, "data")
CALENDAR_DIR = os.path.join(DATA_DIR, "calendar")
DB_PATH = os.path.join(CALENDAR_DIR, "calendar.db")


# ---------------------------------------------------------------------------
# 数据对象 (不使用裸 dict)
# ---------------------------------------------------------------------------
@dataclass
class CalendarEvent:
    """一条日程记录"""
    date: str                       # YYYY-MM-DD
    title: str
    time: str = ""                 # HH:MM, 可空
    description: str = ""
    location: str = ""
    created_time: float = 0.0
    id: int = 0

    @staticmethod
    def from_row(row: Dict[str, Any]) -> "CalendarEvent":
        """由 SqliteTableManager 返回的字段字典构造对象(仅在 DAO 边界使用 dict)"""
        return CalendarEvent(
            id=int(row.get("id", 0)),
            date=row.get("date", ""),
            time=(row.get("time", "") or ""),
            title=(row.get("title", "") or ""),
            description=(row.get("description", "") or ""),
            location=(row.get("location", "") or ""),
            created_time=float(row.get("created_time", 0.0) or 0.0),
        )


# ---------------------------------------------------------------------------
# DAO (基于 duck_utils.sqlite_util)
# ---------------------------------------------------------------------------
class CalendarDao:
    """日程数据的 SQLite 持久化层(DAO)"""

    TABLE = "events"

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        # pkName=None -> 自动创建 id integer primary key autoincrement
        # SqliteTableManager.execute 默认 debug=False(静默, 不打印 SQL), 直接复用即可
        self.manager = SqliteTableManager(db_path, self.TABLE)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        m = self.manager
        m.add_column("date", "text", "")
        m.add_column("time", "text", "")
        m.add_column("title", "text", "")
        m.add_column("description", "text", "")
        m.add_column("location", "text", "")
        m.add_column("created_time", "real", 0.0)
        m.add_index(["date", "time"])

    # ---- 写 ----
    def add(self, ev: CalendarEvent) -> CalendarEvent:
        if not ev.created_time:
            ev.created_time = time.time()
        sql = ("INSERT INTO %s (date, time, title, description, location, created_time) "
                "VALUES (:date, :time, :title, :description, :location, :created_time)") % self.TABLE
        self.manager.execute(sql, parameters={
            "date": ev.date, "time": ev.time, "title": ev.title,
            "description": ev.description, "location": ev.location,
            "created_time": ev.created_time,
        })
        rows = self.manager.execute("SELECT last_insert_rowid() AS id")
        ev.id = int(rows[0]["id"]) if rows else 0
        return ev

    def update(self, eid: int, **changes: Any) -> bool:
        # 仅允许固定白名单列; 列名来自代码常量(非用户输入), 值全部参数化
        allowed = ("date", "time", "title", "description", "location")
        sets, params = [], {}
        for col in allowed:
            if col in changes:
                sets.append("%s = :%s" % (col, col))
                params[col] = changes[col]
        if not sets:
            return False
        params["id"] = eid
        sql = "UPDATE %s SET %s WHERE id = :id" % (self.TABLE, ", ".join(sets))
        self.manager.execute(sql, parameters=params)
        return self.get_by_id(eid) is not None

    def delete(self, eid: int) -> bool:
        if self.get_by_id(eid) is None:
            return False
        self.manager.execute("DELETE FROM %s WHERE id = :id" % self.TABLE,
                             parameters={"id": eid})
        return True

    # ---- 读 ----
    def get_by_id(self, eid: int) -> Optional[CalendarEvent]:
        sql = "SELECT * FROM %s WHERE id = :id" % self.TABLE
        rows = self.manager.execute(sql, parameters={"id": eid})
        return CalendarEvent.from_row(rows[0]) if rows else None

    def list_by_date(self, date_str: str) -> List[CalendarEvent]:
        sql = "SELECT * FROM %s WHERE date = :date ORDER BY time, id" % self.TABLE
        return [CalendarEvent.from_row(r) for r in
                self.manager.execute(sql, parameters={"date": date_str})]

    def list_by_month(self, year: int, month: int) -> List[CalendarEvent]:
        # 通配符 % 作为绑定参数的值传入, 不拼进 SQL 文本
        prefix = "%04d-%02d-" % (year, month)
        sql = "SELECT * FROM %s WHERE date LIKE :pat ORDER BY date, time, id" % self.TABLE
        return [CalendarEvent.from_row(r) for r in
                self.manager.execute(sql, parameters={"pat": prefix + "%"})]

    def list_range(self, start: str, end: str) -> List[CalendarEvent]:
        sql = "SELECT * FROM %s WHERE date >= :start AND date <= :end ORDER BY date, time, id" % self.TABLE
        return [CalendarEvent.from_row(r) for r in
                self.manager.execute(sql, parameters={"start": start, "end": end})]

    def list_upcoming(self, from_date: str, limit: int = 10) -> List[CalendarEvent]:
        sql = "SELECT * FROM %s WHERE date >= :from_date ORDER BY date, time, id LIMIT :lim" % self.TABLE
        return [CalendarEvent.from_row(r) for r in
                self.manager.execute(sql, parameters={"from_date": from_date, "lim": limit})]

    def list_all(self) -> List[CalendarEvent]:
        sql = "SELECT * FROM %s ORDER BY date, time, id" % self.TABLE
        return [CalendarEvent.from_row(r) for r in self.manager.execute(sql)]

    def close(self) -> None:
        self.manager.close()


# 模块级单例, 供各 CLI 子命令共用
dao = CalendarDao()


# ---------------------------------------------------------------------------
# 日期解析
# ---------------------------------------------------------------------------
def _today() -> date:
    return date.today()


def today_str() -> str:
    return _today().strftime("%Y-%m-%d")


def parse_date(text: str) -> str:
    """解析为 'YYYY-MM-DD', 失败抛 ValueError"""
    t = (text or "").strip().lower()
    if t in ("today", "t", "今", "今天"):
        return today_str()
    if t in ("tomorrow", "tmr", "明", "明天"):
        return (_today() + timedelta(days=1)).strftime("%Y-%m-%d")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(t, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # 仅 月-日, 取当前年
    for fmt in ("%m-%d", "%m/%d"):
        try:
            d = datetime.strptime(t, fmt)
            return _today().replace(month=d.month, day=d.day).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError("无法解析日期: %r (支持 today / 2026-07-19 / 07-19 等)" % text)


def parse_month(text: str):
    """解析为 (year, month), 空串表示当前月"""
    t = (text or "").strip()
    if not t:
        d = _today()
        return d.year, d.month
    m = re.match(r"^(\d{4})[-/](\d{1,2})$", t)
    if not m:
        raise ValueError("无法解析月份: %r (支持 2026-07)" % text)
    return int(m.group(1)), int(m.group(2))


# ---------------------------------------------------------------------------
# 展示
# ---------------------------------------------------------------------------
def _disp_width(s: str) -> int:
    """按东亚全角宽度计算字符串的显示列数 (CJK/全角=2, 其余=1)"""
    from unicodedata import east_asian_width
    w = 0
    for ch in s:
        w += 2 if east_asian_width(ch) in ("F", "W") else 1
    return w


def _pad(s: str, width: int, align: str = "left") -> str:
    """按显示宽度把字符串补空格到指定列宽, 支持中文全角对齐"""
    gap = width - _disp_width(s)
    if gap < 0:
        gap = 0
    if align == "right":
        return " " * gap + s
    if align == "center":
        left = gap // 2
        return " " * left + s + " " * (gap - left)
    return s + " " * gap


# 月历每格显示列宽(全角表头占 2 列, 补 1 空格凑成 3)
CELL_W = 3
WEEK_HDR = ["一", "二", "三", "四", "五", "六", "日"]


def _print_event(ev: CalendarEvent, title_w: int = 20) -> None:
    when = ev.date + (" " + ev.time if ev.time else "")
    when = _pad(when, 16)
    title = _pad(ev.title, title_w)
    loc = (" @%s" % ev.location) if ev.location else ""
    desc = ("  - %s" % ev.description) if ev.description else ""
    print("[%d] %s  %s%s%s" % (ev.id, when, title, loc, desc))


def show_month(year: int, month: int) -> None:
    """打印月历, 有日程的日期以 * 标注, 并在下方列出本月日程"""
    events = dao.list_by_month(year, month)
    event_days = set()
    for e in events:
        try:
            event_days.add(int(e.date.split("-")[2]))
        except (IndexError, ValueError):
            pass

    cal = calendar.monthcalendar(year, month)
    print("")
    print("      %d 年 %d 月" % (year, month))
    # 表头每格固定 CELL_W 列宽, 与下方日期格对齐
    print("  " + " ".join(_pad(h, CELL_W, align="right") for h in WEEK_HDR))
    for week in cal:
        cells = []
        for day in week:
            if day == 0:
                cells.append(_pad("", CELL_W))
            else:
                txt = str(day) + ("*" if day in event_days else "")
                cells.append(_pad(txt, CELL_W, align="right"))
        print("  " + " ".join(cells))
    print("  (* 表示该日有日程)")
    print("")
    if events:
        # 标题列宽按本月最长标题自适应, 使列表也对齐
        title_w = max([_disp_width(e.title) for e in events] + [20])
        print("本月日程 (%d 条):" % len(events))
        for e in events:
            _print_event(e, title_w=title_w)
    else:
        print("本月暂无日程")


# ---------------------------------------------------------------------------
# CLI 子命令
# ---------------------------------------------------------------------------
def cmd_add(args: argparse.Namespace) -> None:
    date_str = parse_date(args.date)
    ev = CalendarEvent(
        date=date_str,
        title=args.title,
        time=(args.time or ""),
        description=(args.desc or ""),
        location=(args.location or ""),
        created_time=time.time(),
    )
    ev = dao.add(ev)
    print("已添加日程 #%d: %s %s" % (ev.id, ev.date, ev.title))


def cmd_list(args: argparse.Namespace) -> None:
    if args.all:
        items = dao.list_all()
    elif args.month:
        y, m = parse_month(args.month)
        items = dao.list_by_month(y, m)
    elif args.date:
        items = dao.list_by_date(parse_date(args.date))
    elif args.upcoming is not None:
        n = args.upcoming if args.upcoming > 0 else 10
        items = dao.list_upcoming(today_str(), limit=n)
    else:
        items = dao.list_by_date(today_str())

    if not items:
        print("没有日程")
        return
    print("共 %d 条日程:" % len(items))
    for e in items:
        _print_event(e)


def cmd_show(args: argparse.Namespace) -> None:
    target = (args.target or "").strip()
    if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", target):
        d = parse_date(target)
        y, m = int(d[:4]), int(d[5:7])
    else:
        y, m = parse_month(target)
    show_month(y, m)


def cmd_today(args: argparse.Namespace) -> None:
    items = dao.list_by_date(today_str())
    if not items:
        print("今天没有日程")
        return
    print("今日日程 (%s):" % today_str())
    for e in items:
        _print_event(e)


def cmd_update(args: argparse.Namespace) -> None:
    changes = {}
    if args.date:
        changes["date"] = parse_date(args.date)
    if args.time is not None:
        changes["time"] = args.time
    if args.title:
        changes["title"] = args.title
    if args.desc is not None:
        changes["description"] = args.desc
    if args.location is not None:
        changes["location"] = args.location
    if not changes:
        print("没有任何修改")
        return
    if dao.update(args.id, **changes):
        print("已更新日程 #%d" % args.id)
    else:
        print("未找到日程 #%d" % args.id)


def cmd_delete(args: argparse.Namespace) -> None:
    if dao.delete(args.id):
        print("已删除日程 #%d" % args.id)
    else:
        print("未找到日程 #%d" % args.id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="命令行日历工具 (展示与管理日程)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("示例:\n"
                 "  duck-calendar.py add 2026-07-20 团队周会 --time 14:30 --location 会议室A\n"
                 "  duck-calendar.py add today 健身 --time 19:00\n"
                 "  duck-calendar.py list --upcoming        # 查看未来日程\n"
                 "  duck-calendar.py show 2026-07          # 查看 7 月月历\n"
                 "  duck-calendar.py today                 # 查看今天\n"
                 "  duck-calendar.py update 3 --time 15:00  # 修改 ID=3 的时间\n"
                 "  duck-calendar.py delete 3             # 删除 ID=3"))
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="添加日程",
                           formatter_class=argparse.RawDescriptionHelpFormatter,
                           description=("添加日程。\n"
                                        "日期格式: today / 2026-07-20 / 07-20 等\n"
                                        "示例:\n"
                                        "  duck-calendar.py add 2026-07-20 团队周会 --time 14:30 --location 会议室A\n"
                                        "  duck-calendar.py add today 健身 --time 19:00"))
    p_add.add_argument("date", help="日期(支持 today / 2026-07-20 / 07-20)")
    p_add.add_argument("title", help="日程标题")
    p_add.add_argument("--time", default="", help="时间 HH:MM (可选)")
    p_add.add_argument("--desc", default="", help="说明 (可选)")
    p_add.add_argument("--location", default="", help="地点 (可选)")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="列出日程",
                            formatter_class=argparse.RawDescriptionHelpFormatter,
                            description=("列出日程。默认列出今天; 可用以下选项筛选:\n"
                                         "  --date 指定某天  --month 指定某月  --upcoming [N] 未来 N 条  --all 全部"))
    p_list.add_argument("--date", help="按日期筛选 (如 2026-07-20)")
    p_list.add_argument("--month", help="按月份筛选 (如 2026-07)")
    p_list.add_argument("--upcoming", nargs="?", type=int, const=10, default=None,
                        help="列出从今天起未来的日程, 可跟数量(默认 10)")
    p_list.add_argument("--all", action="store_true", help="列出全部日程")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="查看月历(标注有日程的日期)",
                            formatter_class=argparse.RawDescriptionHelpFormatter,
                            description=("查看月历, 有日程的日期以 * 标注。\n"
                                         "示例: duck-calendar.py show 2026-07"))
    p_show.add_argument("target", nargs="?", default="",
                        help="年月(如 2026-07)或日期(如 2026-07-20), 缺省为当前月")
    p_show.set_defaults(func=cmd_show)

    p_today = sub.add_parser("today", help="查看今天日程")
    p_today.set_defaults(func=cmd_today)

    p_upd = sub.add_parser("update", help="修改日程",
                            formatter_class=argparse.RawDescriptionHelpFormatter,
                            description=("修改指定 ID 的日程, 仅更新给定的字段。\n"
                                         "示例: duck-calendar.py update 3 --time 15:00 --title 改个名"))
    p_upd.add_argument("id", type=int, help="日程 ID(可用 list 查看)")
    p_upd.add_argument("--date", help="新日期")
    p_upd.add_argument("--time", help="新时间 HH:MM")
    p_upd.add_argument("--title", help="新标题")
    p_upd.add_argument("--desc", help="新说明")
    p_upd.add_argument("--location", help="新地点")
    p_upd.set_defaults(func=cmd_update)

    p_del = sub.add_parser("delete", help="删除日程",
                           formatter_class=argparse.RawDescriptionHelpFormatter,
                           description=("删除指定 ID 的日程。\n"
                                        "示例: duck-calendar.py list    # 先查看 ID\n"
                                        "       duck-calendar.py delete 3"))
    p_del.add_argument("id", type=int, help="日程 ID(可用 list 查看)")
    p_del.set_defaults(func=cmd_delete)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        return
    try:
        args.func(args)
    finally:
        dao.close()


if __name__ == "__main__":
    main()
