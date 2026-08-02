# -*- coding: utf-8 -*-
"""duck-browser — 同步 Chrome/Edge/Firefox/Safari 的书签与历史到本地库, 支持搜索与访问统计。

把各浏览器的书签、浏览历史同步到统一的本地 SQLite 库, 之后可以离线做跨浏览器的
模糊搜索与访问排行统计。同步时先给浏览器数据库做一致性快照再读, 因此浏览器开着
也能正常同步, 不会遇到 database is locked。

用法:
    duck-browser list                          # 列出检测到的浏览器与 profile
    duck-browser sync [-b 浏览器] [--profile 名称] [--user-data-dir 目录]
    duck-browser search <关键词...> [-t bookmark|history|all] [-b 浏览器] [-n 20] [--jsonl]
    duck-browser top [--days 7] [-n 10] [--by url|domain] [-b 浏览器] [--all-visits] [--jsonl]
    duck-browser stat                          # 各浏览器条目数与上次同步时间

示例:
    duck-browser sync                          # 同步所有已安装浏览器
    duck-browser sync -b firefox               # 只同步 Firefox
    duck-browser search github issue           # 多个关键词是 AND 关系
    duck-browser search 文档 -t bookmark        # 只搜书签
    duck-browser top --days 30 --by domain     # 最近30天访问最多的域名

说明:
    - 支持的浏览器: chrome, edge, firefox, safari(仅 macOS, 需授予终端"完全磁盘访问权限")
    - 不加 -b 时 sync 会同步所有检测到的浏览器, 单个失败不影响其余
    - sync 是全量覆盖: 只清空并重建被同步浏览器的数据, 其他浏览器的数据不受影响
    - 数据保存在 ~/.duck-rush/data/duck-browser/browser.db, 内含完整浏览历史明文,
      请勿分享该文件
    - top 默认过滤重定向/内嵌页面的访问, 加 --all-visits 可统计全部
    - -h/--help 仅打印帮助并以 0 退出, 不读写数据、不创建文件
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

duck_rush_dir = os.environ.get("DUCK_RUSH_DIR", "")
if duck_rush_dir and duck_rush_dir not in sys.path:
    sys.path.append(duck_rush_dir)

try:
    from duck_utils.os_util import get_command_data_dir, is_mac, is_windows
    from duck_utils.sqlite_util import SqliteTableManager
except ImportError:
    sys.stderr.write("无法导入 duck_utils 模块, 请先执行 `python install.py` 安装后重试。\n")
    sys.exit(1)


CMD_NAME = "duck-browser"
DB_NAME = "browser.db"

# Chromium 时间戳: 1601-01-01 UTC 起的微秒数
CHROME_EPOCH_DIFF = 11644473600.0
# Safari 时间戳: 2001-01-01 UTC 起的秒数
SAFARI_EPOCH_DIFF = 978307200.0

# 在线备份的最长等待时间(秒), 超时后退化为文件复制
BACKUP_TIMEOUT = 5.0

# Chromium transition 高位: SERVER_REDIRECT | CLIENT_REDIRECT
CHROMIUM_REDIRECT_MASK = 0xC0000000
# Firefox visit_type: 5,6=重定向, 7=内嵌资源, 8=框架内跳转
FIREFOX_REDIRECT_TYPES = (5, 6, 7, 8)

BROWSER_NAMES = ("chrome", "edge", "firefox", "safari")


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def to_unix_time(value: Any, epoch_diff: float, unit: float = 1e6) -> float:
    """把浏览器的时间戳换算成 unix 秒。

    各浏览器的 epoch 与单位不同, 统一在这里处理; 空值/非法值一律返回 0.0,
    避免算出 -11644473600 这类穿越到 1601 年的时间。
    """
    if value is None or value == "":
        return 0.0
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return 0.0
    if raw <= 0:
        return 0.0
    return raw / unit - epoch_diff


def unix_to_str(ts: float) -> str:
    """unix 秒格式化为 YYYY-MM-DD HH:MM, 0 或非法值显示为 '-'。"""
    if ts <= 0:
        return "-"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return "-"


def get_domain(url: str) -> str:
    """提取 URL 的域名, 失败返回空串。"""
    try:
        # hostname 已去掉端口与用户名, 且是小写; netloc 不行
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def build_search_text(*parts: str) -> str:
    """拼接可搜索文本并转小写。

    SQLite 内建的 LIKE/LOWER 只折叠 ASCII 大小写, 'CAFÉ' 匹配不到 'Café';
    这里用 Python 的 Unicode 感知 lower() 预先算好, 查询时只比对本列。
    """
    return " ".join(p for p in parts if p).lower()


def like_pattern(keyword: str) -> str:
    """把关键词转成 LIKE 的模式串: 转小写 + 转义通配符。

    不转义的话搜 '100%' 会匹配到所有记录。反斜杠必须最先替换。
    """
    kw = keyword.lower()
    for ch in ("\\", "%", "_"):
        kw = kw.replace(ch, "\\" + ch)
    return "%" + kw + "%"


def build_keyword_clause(column: str, keywords: Sequence[str]) -> Tuple[str, List[str]]:
    """构造多关键词 AND 的 LIKE 条件。

    column 是代码内的常量列名, 关键词一律参数化, 不拼进 SQL 文本。
    """
    parts = ["%s LIKE ? ESCAPE '\\'" % column] * len(keywords)
    return " AND ".join(parts), [like_pattern(k) for k in keywords]


def _disp_width(s: str) -> int:
    """按东亚全角宽度计算显示列数 (CJK/全角=2, 其余=1)。"""
    from unicodedata import east_asian_width
    width = 0
    for ch in s:
        width += 2 if east_asian_width(ch) in ("F", "W") else 1
    return width


def _pad(s: str, width: int) -> str:
    """按显示宽度左对齐补空格, 支持中文全角。"""
    gap = width - _disp_width(s)
    return s + " " * max(gap, 0)


def _truncate(s: str, width: int) -> str:
    """按显示宽度截断, 超长时以 .. 结尾。"""
    if _disp_width(s) <= width:
        return s
    out = ""
    used = 0
    for ch in s:
        cw = 2 if _disp_width(ch) == 2 else 1
        if used + cw > width - 2:
            break
        out += ch
        used += cw
    return out + ".."


# ANSI 高亮: 粗体红。仅在终端(或显式 --color)下使用, 管道/--jsonl 不加。
HIGHLIGHT_ON = "\033[1;31m"
HIGHLIGHT_OFF = "\033[0m"


def highlight(text: str, keywords: Sequence[str]) -> str:
    """把命中的关键词(大小写不敏感, 含非 ASCII)用 ANSI 粗体红标出。

    与搜索保持一致: 关键词与待匹配文本都先 .lower() 再比位置, 这样 Café 也能
    命中 café。多个关键词可能重叠(如 'py' 与 'python'), 这里长词优先,
    已覆盖的字符不再二次包裹, 避免出现嵌套转义码。
    """
    if not text or not keywords:
        return text
    low = text.lower()
    covered = [False] * len(text)
    spans: List[Tuple[int, int]] = []
    for kw in sorted(set(keywords), key=len, reverse=True):
        kw = kw.lower()
        if not kw:
            continue
        start = 0
        while True:
            idx = low.find(kw, start)
            if idx < 0:
                break
            end = idx + len(kw)
            if not any(covered[idx:end]):
                spans.append((idx, end))
                for i in range(idx, end):
                    covered[i] = True
            start = end
    if not spans:
        return text
    spans.sort()
    out: List[str] = []
    pos = 0
    for s, e in spans:
        out.append(text[pos:s])
        out.append(HIGHLIGHT_ON + text[s:e] + HIGHLIGHT_OFF)
        pos = e
    out.append(text[pos:])
    return "".join(out)


def setup_stdout() -> None:
    """终端编码(如 Windows GBK)无法表示网页标题里的 emoji 时以替换符兜底。"""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(errors="replace")


def print_jsonl(rows: List[Dict[str, Any]]) -> None:
    """每行一个 JSON 对象, 供其他程序解析。"""
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------
@dataclass
class Bookmark:
    """一条书签"""
    browser: str = ""
    profile: str = ""
    guid: str = ""
    folder: str = ""
    name: str = ""
    url: str = ""
    date_added: float = 0.0

    def as_row(self) -> tuple:
        return (self.browser, self.profile, self.guid, self.folder, self.name,
                self.url, get_domain(self.url), self.date_added,
                build_search_text(self.name, self.url, self.folder))


@dataclass
class UrlRow:
    """一条历史 URL 的汇总"""
    browser: str = ""
    profile: str = ""
    url_id: int = 0
    url: str = ""
    title: str = ""
    visit_count: int = 0
    typed_count: int = 0
    last_visit_time: float = 0.0

    def as_row(self) -> tuple:
        return (self.browser, self.profile, self.url_id, self.url, self.title,
                get_domain(self.url), self.visit_count, self.typed_count,
                self.last_visit_time, build_search_text(self.title, self.url))


@dataclass
class BrowserProfile:
    """一个浏览器的一份 profile"""
    browser: str
    name: str
    history_path: str
    bookmarks_path: str = ""


@dataclass
class BrowserSnapshot:
    """从浏览器读出的一份快照。

    visits 用生成器承载, 8 万条访问明细不会全部落到内存。
    """
    browser: str
    profile: str
    bookmarks: List[Bookmark] = field(default_factory=list)
    urls: List[UrlRow] = field(default_factory=list)
    visit_rows: Iterator[tuple] = iter(())


@dataclass
class SyncStat:
    """一个浏览器的同步结果"""
    browser: str
    profile: str = ""
    bookmarks: int = 0
    urls: int = 0
    visits: int = 0
    elapsed: float = 0.0
    error: str = ""


@dataclass
class SearchHit:
    """一条搜索结果"""
    kind: str
    browser: str
    title: str
    url: str
    extra: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "browser": self.browser, "title": self.title,
                "url": self.url, "extra": self.extra, "time": unix_to_str(self.timestamp)}


@dataclass
class TopRow:
    """一条排行统计"""
    key: str
    title: str = ""
    browser: str = ""
    visits: int = 0
    urls: int = 0
    last_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"key": self.key, "title": self.title, "browser": self.browser,
                "visits": self.visits, "urls": self.urls,
                "last_time": unix_to_str(self.last_time)}


@dataclass
class SearchRequest:
    """search 子命令的参数"""
    keywords: List[str]
    kind: str = "all"
    browser: Optional[str] = None
    limit: int = 20


@dataclass
class TopRequest:
    """top 子命令的参数"""
    days: int = 7
    limit: int = 10
    by: str = "url"
    browser: Optional[str] = None
    all_visits: bool = False


class BrowserError(Exception):
    """浏览器数据读取失败"""


# ---------------------------------------------------------------------------
# 数据库快照
# ---------------------------------------------------------------------------
class DbSnapshot:
    """把浏览器的 sqlite 库复制到临时目录再读, 避开浏览器持有的写锁。

    优先用 sqlite 的在线备份 API: 它逐页拷贝并在源库被改动时自动重启, 产出的是
    事务一致的快照; shutil.copy2 是非原子的, 拷到一半源库被写就会得到撕裂的文件。
    浏览器持续写入导致备份始终拿不到锁时(实测 Edge 常态如此), 退化为文件复制,
    再用 quick_check 确认复制结果可用。
    """

    def __init__(self, src_path: str) -> None:
        self.src_path = src_path
        self.tmp_dir = ""
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        if not os.path.exists(self.src_path):
            raise BrowserError("数据库不存在: %s" % self.src_path)
        self.tmp_dir = tempfile.mkdtemp(prefix="duck_browser_")
        snap_path = os.path.join(self.tmp_dir, os.path.basename(self.src_path))
        last_error: Optional[Exception] = None
        for _ in range(2):
            try:
                self.conn = self._open_snapshot(snap_path)
                return self.conn
            except (sqlite3.Error, BrowserError) as e:
                last_error = e
                # 撕裂或加锁多为瞬时状态, 清掉半成品重试一次
                self._remove_snapshot(snap_path)
        self.__exit__(None, None, None)
        raise BrowserError("读取失败(%s), 请关闭浏览器后重试: %s" % (last_error, self.src_path))

    def __exit__(self, *exc: Any) -> None:
        # Windows 上未关闭连接就删目录会报 WinError 32
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        if self.tmp_dir:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
            self.tmp_dir = ""

    def _open_snapshot(self, snap_path: str) -> sqlite3.Connection:
        try:
            return self._via_backup(snap_path)
        except (sqlite3.Error, BrowserError):
            # 浏览器正在持续写入时备份拿不到锁, 退化为文件复制
            self._remove_snapshot(snap_path)
            return self._via_copy(snap_path)

    def _remove_snapshot(self, snap_path: str) -> None:
        """清掉上一次尝试留下的半成品(备份产物会继承源库的日志模式)。"""
        for suffix in ("", "-wal", "-shm", "-journal"):
            try:
                os.remove(snap_path + suffix)
            except OSError:
                pass

    def _via_backup(self, snap_path: str) -> sqlite3.Connection:
        """sqlite 在线备份, 产出事务一致的快照。

        必须用 progress 回调实现超时: 浏览器持续写入时 backup 会在 C 层无限重试
        SQLITE_BUSY, 既不受 connect(timeout=) 约束, 也打断不了 interrupt(),
        只有从回调里抛异常才能中止。
        """
        deadline = time.time() + BACKUP_TIMEOUT

        def on_progress(status: int, remaining: int, total: int) -> None:
            if time.time() > deadline:
                raise BrowserError("备份超时")

        uri = Path(self.src_path).as_uri() + "?mode=ro"
        src = sqlite3.connect(uri, uri=True, timeout=5.0)
        try:
            dst = sqlite3.connect(snap_path)
            try:
                # 分批拷贝, 让 progress 回调有机会检查超时
                src.backup(dst, pages=2048, progress=on_progress)
            finally:
                dst.close()
        finally:
            src.close()
        return sqlite3.connect(snap_path)

    def _via_copy(self, snap_path: str) -> sqlite3.Connection:
        """退化方案: 复制主库与 -wal。

        不复制 -shm: 它是 wal 的共享内存索引, 纯派生数据, sqlite 会自动从 wal 重建;
        而从活跃进程复制来的 -shm 与复制到的 -wal 版本必然不同步, 反而可能触发
        无谓的恢复流程甚至 database disk image is malformed。
        """
        shutil.copy2(self.src_path, snap_path)
        for suffix in ("-wal", "-journal"):
            side = self.src_path + suffix
            if os.path.exists(side):
                shutil.copy2(side, snap_path + suffix)
        # 带 wal 的快照不能用 immutable=1 打开, 否则读不到最新的未 checkpoint 数据
        conn = sqlite3.connect(snap_path)
        conn.execute("PRAGMA quick_check").fetchone()
        return conn


# ---------------------------------------------------------------------------
# 浏览器后端
# ---------------------------------------------------------------------------
class BrowserBackend:
    """浏览器数据读取的抽象接口"""

    name = ""

    def detect_profiles(self, root: Optional[str] = None) -> List[BrowserProfile]:
        """列出可用的 profile, 浏览器未安装时返回空列表。"""
        raise NotImplementedError

    def read_snapshot(self, profile: BrowserProfile) -> BrowserSnapshot:
        """读取该 profile 的书签与历史。"""
        raise NotImplementedError


class ChromiumBackend(BrowserBackend):
    """Chrome / Edge 等 Chromium 系浏览器, 数据结构完全一致, 只有安装路径不同。"""

    def __init__(self, name: str, win_rel: str, mac_rel: str, linux_rel: str) -> None:
        self.name = name
        self.win_rel = win_rel
        self.mac_rel = mac_rel
        self.linux_rel = linux_rel

    def default_root(self) -> str:
        home = os.path.expanduser("~")
        if is_windows():
            local = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
            return os.path.join(local, *self.win_rel.split("/"))
        if is_mac():
            return os.path.join(home, "Library", "Application Support",
                                *self.mac_rel.split("/"))
        return os.path.join(home, *self.linux_rel.split("/"))

    def detect_profiles(self, root: Optional[str] = None) -> List[BrowserProfile]:
        user_data_dir = root or self.default_root()
        if not os.path.isdir(user_data_dir):
            return []
        result = []
        for entry in sorted(os.listdir(user_data_dir)):
            if entry != "Default" and not entry.startswith("Profile "):
                continue
            history = os.path.join(user_data_dir, entry, "History")
            if not os.path.exists(history):
                continue
            result.append(BrowserProfile(
                browser=self.name,
                name=entry,
                history_path=history,
                bookmarks_path=os.path.join(user_data_dir, entry, "Bookmarks"),
            ))
        return result

    def read_snapshot(self, profile: BrowserProfile) -> BrowserSnapshot:
        snap = BrowserSnapshot(browser=self.name, profile=profile.name)
        snap.bookmarks = self._read_bookmarks(profile)
        with DbSnapshot(profile.history_path) as conn:
            snap.urls = self._read_urls(conn, profile)
            snap.visit_rows = iter(self._read_visits(conn))
        return snap

    def _read_urls(self, conn: sqlite3.Connection,
                   profile: BrowserProfile) -> List[UrlRow]:
        sql = ("SELECT id, url, title, visit_count, typed_count, last_visit_time "
               "FROM urls WHERE hidden = 0")
        result = []
        for row in conn.execute(sql):
            result.append(UrlRow(
                browser=self.name,
                profile=profile.name,
                url_id=int(row[0]),
                url=row[1] or "",
                title=row[2] or "",
                visit_count=int(row[3] or 0),
                typed_count=int(row[4] or 0),
                last_visit_time=to_unix_time(row[5], CHROME_EPOCH_DIFF),
            ))
        return result

    def _read_visits(self, conn: sqlite3.Connection) -> List[tuple]:
        sql = ("SELECT v.url, v.visit_time, v.transition FROM visits v "
               "JOIN urls u ON u.id = v.url WHERE u.hidden = 0")
        result = []
        for url_id, visit_time, transition in conn.execute(sql):
            is_redirect = 1 if (int(transition or 0) & CHROMIUM_REDIRECT_MASK) else 0
            result.append((self.name, int(url_id),
                           to_unix_time(visit_time, CHROME_EPOCH_DIFF), is_redirect))
        return result

    def _read_bookmarks(self, profile: BrowserProfile) -> List[Bookmark]:
        path = profile.bookmarks_path
        data = self._load_bookmark_json(path)
        if data is None:
            return []
        result: List[Bookmark] = []
        roots = data.get("roots", {})
        if not isinstance(roots, dict):
            return []
        for key, node in roots.items():
            # roots 里混有字符串值的兄弟键, 如 sync_transaction_version
            if isinstance(node, dict):
                self._walk_node(node, "", profile, result)
        return result

    def _load_bookmark_json(self, path: str) -> Optional[Dict[str, Any]]:
        """读书签 JSON; Chrome 写入瞬间可能读到半截, 回退到 .bak。"""
        for candidate in (path, path + ".bak"):
            if not os.path.exists(candidate):
                continue
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except (OSError, ValueError):
                continue
        return None

    def _walk_node(self, node: Dict[str, Any], folder: str,
                   profile: BrowserProfile, out: List[Bookmark]) -> None:
        node_type = node.get("type")
        name = node.get("name") or ""
        if node_type == "url":
            out.append(Bookmark(
                browser=self.name,
                profile=profile.name,
                guid=str(node.get("guid") or ""),
                folder=folder,
                name=name,
                url=node.get("url") or "",
                # date_added 是字符串形式的 Chromium 时间戳, 可能是 "" / "0"
                date_added=to_unix_time(node.get("date_added"), CHROME_EPOCH_DIFF),
            ))
            return
        sub_folder = folder + "/" + name if folder else name
        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    self._walk_node(child, sub_folder, profile, out)


class FirefoxBackend(BrowserBackend):
    """Firefox: 书签与历史都在 places.sqlite 里, 时间戳是 unix 微秒。"""

    name = "firefox"
    # moz_bookmarks 的根文件夹, 展示时换成中文
    ROOT_TITLES = {
        "menu": "书签菜单", "toolbar": "书签栏",
        "unfiled": "其他书签", "mobile": "移动设备书签",
    }

    def default_root(self) -> str:
        home = os.path.expanduser("~")
        if is_windows():
            roaming = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
            return os.path.join(roaming, "Mozilla", "Firefox")
        if is_mac():
            return os.path.join(home, "Library", "Application Support", "Firefox")
        return os.path.join(home, ".mozilla", "firefox")

    def detect_profiles(self, root: Optional[str] = None) -> List[BrowserProfile]:
        firefox_dir = root or self.default_root()
        ini_path = os.path.join(firefox_dir, "profiles.ini")
        if not os.path.exists(ini_path):
            return []
        paths = self._parse_profiles_ini(ini_path, firefox_dir)
        result = []
        for name, profile_dir in paths:
            places = os.path.join(profile_dir, "places.sqlite")
            if os.path.exists(places):
                result.append(BrowserProfile(browser=self.name, name=name,
                                             history_path=places))
        return result

    def _parse_profiles_ini(self, ini_path: str,
                            firefox_dir: str) -> List[Tuple[str, str]]:
        """解析 profiles.ini, 默认 profile 排在最前。

        优先级: [InstallXXX] 段的 Default > [ProfileN] 里 Default=1 > 第一个 profile。
        实测中 Default=1 可能指向一个从未使用的空 profile, 而 Install 段才指向
        真正在用的那个, 所以 Install 段优先。
        """
        import configparser
        # 段名(InstallXXX/ProfileN)不会被转换, 键名读写都会统一小写, 故可直接用原名查询
        parser = configparser.ConfigParser()
        try:
            parser.read(ini_path, encoding="utf-8")
        except (OSError, configparser.Error):
            return []

        install_default = ""
        flagged_default = ""
        profiles: List[Tuple[str, str]] = []
        for section in parser.sections():
            if section.startswith("Install"):
                install_default = parser.get(section, "Default", fallback="")
                continue
            if not section.startswith("Profile"):
                continue
            rel_path = parser.get(section, "Path", fallback="")
            if not rel_path:
                continue
            is_relative = parser.get(section, "IsRelative", fallback="1") == "1"
            full = os.path.join(firefox_dir, *rel_path.split("/")) if is_relative else rel_path
            name = parser.get(section, "Name", fallback=os.path.basename(full))
            profiles.append((name, full))
            if parser.get(section, "Default", fallback="") == "1":
                flagged_default = rel_path

        preferred = install_default or flagged_default
        if preferred:
            target = os.path.join(firefox_dir, *preferred.split("/"))
            profiles.sort(key=lambda item: os.path.normpath(item[1]) != os.path.normpath(target))
        return profiles

    def read_snapshot(self, profile: BrowserProfile) -> BrowserSnapshot:
        snap = BrowserSnapshot(browser=self.name, profile=profile.name)
        with DbSnapshot(profile.history_path) as conn:
            snap.urls = self._read_urls(conn, profile)
            snap.visit_rows = iter(self._read_visits(conn))
            snap.bookmarks = self._read_bookmarks(conn, profile)
        return snap

    def _read_urls(self, conn: sqlite3.Connection,
                   profile: BrowserProfile) -> List[UrlRow]:
        sql = ("SELECT id, url, title, visit_count, typed, last_visit_date "
               "FROM moz_places WHERE hidden = 0")
        result = []
        for row in conn.execute(sql):
            result.append(UrlRow(
                browser=self.name,
                profile=profile.name,
                url_id=int(row[0]),
                url=row[1] or "",
                title=row[2] or "",
                visit_count=int(row[3] or 0),
                typed_count=int(row[4] or 0),
                last_visit_time=to_unix_time(row[5], 0.0),
            ))
        return result

    def _read_visits(self, conn: sqlite3.Connection) -> List[tuple]:
        sql = ("SELECT v.place_id, v.visit_date, v.visit_type FROM moz_historyvisits v "
               "JOIN moz_places p ON p.id = v.place_id WHERE p.hidden = 0")
        result = []
        for place_id, visit_date, visit_type in conn.execute(sql):
            is_redirect = 1 if int(visit_type or 0) in FIREFOX_REDIRECT_TYPES else 0
            result.append((self.name, int(place_id),
                           to_unix_time(visit_date, 0.0), is_redirect))
        return result

    def _read_bookmarks(self, conn: sqlite3.Connection,
                        profile: BrowserProfile) -> List[Bookmark]:
        # type=1 是书签, type=2 是文件夹
        folders: Dict[int, Tuple[int, str]] = {}
        for bid, parent, title, guid in conn.execute(
                "SELECT id, parent, title, guid FROM moz_bookmarks WHERE type = 2"):
            root_key = (guid or "").rstrip("_")
            name = self.ROOT_TITLES.get(root_key, title or "")
            folders[int(bid)] = (int(parent or 0), name)

        sql = ("SELECT b.guid, b.title, b.dateAdded, b.parent, p.url, p.title "
               "FROM moz_bookmarks b JOIN moz_places p ON p.id = b.fk WHERE b.type = 1")
        result = []
        for guid, title, date_added, parent, url, page_title in conn.execute(sql):
            result.append(Bookmark(
                browser=self.name,
                profile=profile.name,
                guid=guid or "",
                folder=self._folder_path(folders, int(parent or 0)),
                name=title or page_title or "",
                url=url or "",
                date_added=to_unix_time(date_added, 0.0),
            ))
        return result

    def _folder_path(self, folders: Dict[int, Tuple[int, str]], parent: int) -> str:
        """自底向上拼出文件夹路径。"""
        names: List[str] = []
        current = parent
        # 根节点 root________ 的 title 为空, 自然被过滤掉
        while current in folders and len(names) < 32:
            next_parent, name = folders[current]
            if name:
                names.append(name)
            if next_parent == current:
                break
            current = next_parent
        return "/".join(reversed(names))


class SafariBackend(BrowserBackend):
    """Safari (仅 macOS)。

    注意: 本后端按 Safari 的已知数据结构实现, 未在 macOS 上实测。Safari 的数据目录
    受 macOS TCC 保护, 需要在"系统设置 - 隐私与安全性 - 完全磁盘访问权限"里
    授权终端, 否则会报权限错误。
    """

    name = "safari"

    def default_root(self) -> str:
        return os.path.join(os.path.expanduser("~"), "Library", "Safari")

    def detect_profiles(self, root: Optional[str] = None) -> List[BrowserProfile]:
        safari_dir = root or self.default_root()
        if root is None and not is_mac():
            return []
        history = os.path.join(safari_dir, "History.db")
        if not os.path.exists(history):
            return []
        return [BrowserProfile(
            browser=self.name,
            name="Default",
            history_path=history,
            bookmarks_path=os.path.join(safari_dir, "Bookmarks.plist"),
        )]

    def read_snapshot(self, profile: BrowserProfile) -> BrowserSnapshot:
        snap = BrowserSnapshot(browser=self.name, profile=profile.name)
        snap.bookmarks = self._read_bookmarks(profile)
        with DbSnapshot(profile.history_path) as conn:
            snap.urls = self._read_urls(conn, profile)
            snap.visit_rows = iter(self._read_visits(conn))
        return snap

    def _read_urls(self, conn: sqlite3.Connection,
                   profile: BrowserProfile) -> List[UrlRow]:
        sql = ("SELECT i.id, i.url, i.visit_count, "
               "  (SELECT v.title FROM history_visits v WHERE v.history_item = i.id "
               "     AND v.title IS NOT NULL ORDER BY v.visit_time DESC LIMIT 1), "
               "  (SELECT MAX(v.visit_time) FROM history_visits v WHERE v.history_item = i.id) "
               "FROM history_items i")
        result = []
        for row in conn.execute(sql):
            result.append(UrlRow(
                browser=self.name,
                profile=profile.name,
                url_id=int(row[0]),
                url=row[1] or "",
                title=row[3] or "",
                visit_count=int(row[2] or 0),
                typed_count=0,
                last_visit_time=to_unix_time(row[4], -SAFARI_EPOCH_DIFF, unit=1.0),
            ))
        return result

    def _read_visits(self, conn: sqlite3.Connection) -> List[tuple]:
        sql = "SELECT history_item, visit_time, redirect_source FROM history_visits"
        result = []
        for item_id, visit_time, redirect_source in conn.execute(sql):
            is_redirect = 1 if redirect_source is not None else 0
            result.append((self.name, int(item_id),
                           to_unix_time(visit_time, -SAFARI_EPOCH_DIFF, unit=1.0),
                           is_redirect))
        return result

    def _read_bookmarks(self, profile: BrowserProfile) -> List[Bookmark]:
        import plistlib
        path = profile.bookmarks_path
        if not os.path.exists(path):
            return []
        try:
            with open(path, "rb") as f:
                data = plistlib.load(f)
        except (OSError, ValueError):
            return []
        result: List[Bookmark] = []
        if isinstance(data, dict):
            self._walk_node(data, "", profile, result)
        return result

    def _walk_node(self, node: Dict[str, Any], folder: str,
                   profile: BrowserProfile, out: List[Bookmark]) -> None:
        node_type = node.get("WebBookmarkType")
        if node_type == "WebBookmarkTypeLeaf":
            uri_dict = node.get("URIDictionary")
            title = ""
            if isinstance(uri_dict, dict):
                title = str(uri_dict.get("title") or "")
            out.append(Bookmark(
                browser=self.name,
                profile=profile.name,
                guid=str(node.get("WebBookmarkUUID") or ""),
                folder=folder,
                name=title,
                url=str(node.get("URLString") or ""),
            ))
            return
        title = str(node.get("Title") or "")
        sub_folder = folder + "/" + title if folder and title else (title or folder)
        children = node.get("Children")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    self._walk_node(child, sub_folder, profile, out)


def all_backends() -> List[BrowserBackend]:
    """所有支持的浏览器后端。"""
    return [
        ChromiumBackend("chrome", "Google/Chrome/User Data",
                        "Google/Chrome", ".config/google-chrome"),
        ChromiumBackend("edge", "Microsoft/Edge/User Data",
                        "Microsoft Edge", ".config/microsoft-edge"),
        FirefoxBackend(),
        SafariBackend(),
    ]


def get_backend(name: str) -> Optional[BrowserBackend]:
    for backend in all_backends():
        if backend.name == name:
            return backend
    return None


# ---------------------------------------------------------------------------
# 本地存储
# ---------------------------------------------------------------------------
SQL_INSERT_BOOKMARK = (
    "INSERT INTO bookmarks (browser, profile, guid, folder, name, url, domain, "
    "date_added, search_text) VALUES (?,?,?,?,?,?,?,?,?)")

SQL_INSERT_URL = (
    "INSERT INTO urls (browser, profile, url_id, url, title, domain, visit_count, "
    "typed_count, last_visit_time, search_text) VALUES (?,?,?,?,?,?,?,?,?,?)")

SQL_INSERT_VISIT = (
    "INSERT INTO visits (browser, url_id, visit_time, is_redirect) VALUES (?,?,?,?)")


def get_db_path() -> str:
    """本地库路径, 用到时才创建目录(-h 场景不能有副作用)。"""
    return os.path.join(get_command_data_dir(CMD_NAME), DB_NAME)


class BrowserStore:
    """本地 SQLite 存储层"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or get_db_path()
        is_new = not os.path.exists(self.db_path)
        self._ensure_schema()
        if is_new and not is_windows():
            # 库里是完整浏览历史明文, 限制为仅本人可读
            try:
                os.chmod(self.db_path, 0o600)
            except OSError:
                pass

    def _ensure_schema(self) -> None:
        """建表补列建索引。

        SqliteTableManager 每次 execute 都会 commit, 只适合这种一次性的 DDL;
        批量数据写入走 self.conn 的单事务。
        """
        with SqliteTableManager(self.db_path, "meta", pkName="key", pkType="text") as m:
            m.add_column("value", "text", "")

        with SqliteTableManager(self.db_path, "bookmarks") as m:
            for col in ("browser", "profile", "guid", "folder", "name", "url",
                        "domain", "search_text"):
                m.add_column(col, "text", "")
            m.add_column("date_added", "real", 0.0)
            m.add_index("browser")
            m.add_index("search_text")

        with SqliteTableManager(self.db_path, "urls") as m:
            for col in ("browser", "profile", "url", "title", "domain", "search_text"):
                m.add_column(col, "text", "")
            for col in ("url_id", "visit_count", "typed_count"):
                m.add_column(col, "int", 0)
            m.add_column("last_visit_time", "real", 0.0)
            m.add_index(["browser", "url_id"])
            m.add_index("search_text")

        with SqliteTableManager(self.db_path, "visits") as m:
            m.add_column("browser", "text", "")
            m.add_column("url_id", "int", 0)
            m.add_column("visit_time", "real", 0.0)
            m.add_column("is_redirect", "int", 0)
            m.add_index(["browser", "url_id"])
            m.add_index("visit_time")

        self.manager = SqliteTableManager(self.db_path, "meta",
                                          pkName="key", pkType="text")
        conn: sqlite3.Connection = self.manager.db
        # 交给下面的显式 BEGIN 管理事务
        conn.isolation_level = None
        self.conn = conn

    def replace_browser(self, snap: BrowserSnapshot) -> SyncStat:
        """全量覆盖某个浏览器的数据, 其他浏览器不受影响。"""
        start = time.time()
        stat = SyncStat(browser=snap.browser, profile=snap.profile)
        counter = _RowCounter()
        # BEGIN IMMEDIATE 提前拿到写锁, 避免写到一半才发现 SQLITE_BUSY
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            for table in ("bookmarks", "urls", "visits"):
                self.conn.execute("DELETE FROM %s WHERE browser = ?" % table,
                                  (snap.browser,))
            self.conn.executemany(SQL_INSERT_BOOKMARK,
                                  (b.as_row() for b in snap.bookmarks))
            self.conn.executemany(SQL_INSERT_URL, (u.as_row() for u in snap.urls))
            self.conn.executemany(SQL_INSERT_VISIT, counter.wrap(snap.visit_rows))
            self.conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                ("last_sync:" + snap.browser, str(time.time())))
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        stat.bookmarks = len(snap.bookmarks)
        stat.urls = len(snap.urls)
        stat.visits = counter.count
        stat.elapsed = time.time() - start
        return stat

    def search(self, req: SearchRequest) -> List[SearchHit]:
        hits: List[SearchHit] = []
        if req.kind in ("all", "bookmark"):
            hits.extend(self._search_bookmarks(req))
        if req.kind in ("all", "history"):
            hits.extend(self._search_history(req))
        hits.sort(key=lambda h: h.timestamp, reverse=True)
        return hits[:req.limit]

    def _search_bookmarks(self, req: SearchRequest) -> List[SearchHit]:
        clause, params = build_keyword_clause("search_text", req.keywords)
        where = [clause]
        if req.browser:
            where.append("browser = ?")
            params.append(req.browser)
        sql = ("SELECT browser, name, url, folder, date_added FROM bookmarks "
               "WHERE %s ORDER BY date_added DESC LIMIT ?" % " AND ".join(where))
        rows = self.conn.execute(sql, params + [req.limit]).fetchall()
        return [SearchHit(kind="bookmark", browser=r[0], title=r[1], url=r[2],
                          extra=r[3], timestamp=r[4]) for r in rows]

    def _search_history(self, req: SearchRequest) -> List[SearchHit]:
        clause, params = build_keyword_clause("search_text", req.keywords)
        where = [clause]
        if req.browser:
            where.append("browser = ?")
            params.append(req.browser)
        sql = ("SELECT browser, title, url, visit_count, last_visit_time FROM urls "
               "WHERE %s ORDER BY last_visit_time DESC LIMIT ?" % " AND ".join(where))
        rows = self.conn.execute(sql, params + [req.limit]).fetchall()
        return [SearchHit(kind="history", browser=r[0], title=r[1], url=r[2],
                          extra="%d 次访问" % (r[3] or 0), timestamp=r[4])
                for r in rows]

    def top(self, req: TopRequest) -> List[TopRow]:
        # days=0 表示不限时间, 用 since=0 而不是改 SQL 分支
        since = time.time() - req.days * 86400 if req.days > 0 else 0.0
        where = ["v.visit_time >= :since"]
        params: Dict[str, Any] = {"since": since, "limit": req.limit}
        if not req.all_visits:
            where.append("v.is_redirect = 0")
        if req.browser:
            where.append("v.browser = :browser")
            params["browser"] = req.browser
        if req.by == "domain":
            where.append("u.domain <> ''")
            sql = ("SELECT u.domain, '', u.browser, COUNT(*), COUNT(DISTINCT v.url_id), "
                   "MAX(v.visit_time) FROM visits v "
                   "JOIN urls u ON v.browser = u.browser AND v.url_id = u.url_id "
                   "WHERE %s GROUP BY u.browser, u.domain "
                   "ORDER BY 4 DESC, 6 DESC LIMIT :limit" % " AND ".join(where))
        else:
            sql = ("SELECT u.url, u.title, u.browser, COUNT(*), 1, MAX(v.visit_time) "
                   "FROM visits v "
                   "JOIN urls u ON v.browser = u.browser AND v.url_id = u.url_id "
                   "WHERE %s GROUP BY v.browser, v.url_id "
                   "ORDER BY 4 DESC, 6 DESC LIMIT :limit" % " AND ".join(where))
        rows = self.conn.execute(sql, params).fetchall()
        return [TopRow(key=r[0], title=r[1] or "", browser=r[2], visits=int(r[3]),
                       urls=int(r[4]), last_time=r[5] or 0.0) for r in rows]

    def stat(self) -> List[Dict[str, Any]]:
        """各浏览器的条目数与上次同步时间"""
        result = []
        for name in BROWSER_NAMES:
            counts = {}
            for table in ("bookmarks", "urls", "visits"):
                row = self.conn.execute(
                    "SELECT COUNT(1) FROM %s WHERE browser = ?" % table,
                    (name,)).fetchone()
                counts[table] = int(row[0]) if row else 0
            if not any(counts.values()):
                continue
            counts["browser"] = name  # type: ignore[assignment]
            counts["last_sync"] = self.last_sync_time(name)  # type: ignore[assignment]
            result.append(dict(counts))
        return result

    def last_sync_time(self, browser: str) -> float:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?",
                                ("last_sync:" + browser,)).fetchone()
        if not row:
            return 0.0
        try:
            return float(row[0])
        except (TypeError, ValueError):
            return 0.0

    def is_empty(self) -> bool:
        row = self.conn.execute("SELECT COUNT(1) FROM urls").fetchone()
        return not row or int(row[0]) == 0

    def close(self) -> None:
        self.manager.close()


class _RowCounter:
    """边遍历边计数, 让 executemany 仍然可以吃生成器而不必先落地成列表。"""

    def __init__(self) -> None:
        self.count = 0

    def wrap(self, rows: Iterator[tuple]) -> Iterator[tuple]:
        for row in rows:
            self.count += 1
            yield row


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------
def print_search_hits(hits: List[SearchHit], keywords: Sequence[str] = (),
                      color: bool = True) -> None:
    if not hits:
        print("没有匹配的记录")
        return
    kind_label = {"bookmark": "书签", "history": "历史"}
    mark = highlight if color else (lambda t, _k: t)
    for hit in hits:
        head = "[%s/%s]" % (kind_label.get(hit.kind, hit.kind), hit.browser)
        # 先按显示宽度截断(纯文本), 再高亮, 避免转义码干扰对齐
        title = mark(_truncate(hit.title or "(无标题)", 60), keywords)
        print("%s %s" % (_pad(head, 14), title))
        print("    %s" % mark(hit.url, keywords))
        detail = [x for x in (hit.extra, unix_to_str(hit.timestamp)) if x and x != "-"]
        if detail:
            print("    %s" % mark("  ".join(detail), keywords))
    print("\n共 %d 条" % len(hits))


def print_top_rows(rows: List[TopRow], req: TopRequest) -> None:
    if not rows:
        print("没有统计数据, 请先执行 `duck-browser sync`")
        return
    scope = "最近 %d 天" % req.days if req.days > 0 else "全部历史"
    unit = "域名" if req.by == "domain" else "页面"
    print("%s访问最多的 %d 个%s:\n" % (scope, len(rows), unit))
    key_width = 62
    for index, row in enumerate(rows):
        label = row.key if req.by == "domain" else (row.title or row.key)
        print("%2d. %s %6d 次  [%s]" % (
            index + 1, _pad(_truncate(label, key_width), key_width),
            row.visits, row.browser))
        if req.by == "domain":
            print("    %d 个页面  最近 %s" % (row.urls, unix_to_str(row.last_time)))
        else:
            print("    %s" % _truncate(row.key, 76))


def print_sync_stats(stats: List[SyncStat]) -> None:
    ok = [s for s in stats if not s.error]
    failed = [s for s in stats if s.error]
    for stat in ok:
        print("%s (%s): 书签 %d, 网址 %d, 访问 %d, 耗时 %.1fs" % (
            stat.browser, stat.profile, stat.bookmarks, stat.urls,
            stat.visits, stat.elapsed))
    for stat in failed:
        print("%s: 同步失败 - %s" % (stat.browser, stat.error))
    if ok:
        print("\n同步完成: %d 个浏览器, 共 %d 条书签 / %d 条网址 / %d 条访问" % (
            len(ok), sum(s.bookmarks for s in ok), sum(s.urls for s in ok),
            sum(s.visits for s in ok)))


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------
def resolve_profiles(browser: Optional[str], profile_name: Optional[str],
                     user_data_dir: Optional[str]) -> List[BrowserProfile]:
    """按参数解析出要同步的 profile 列表, 每个浏览器只取一个。"""
    backends = all_backends() if not browser else [b for b in all_backends()
                                                   if b.name == browser]
    result = []
    for backend in backends:
        profiles = backend.detect_profiles(user_data_dir)
        if not profiles:
            continue
        if profile_name:
            profiles = [p for p in profiles if p.name == profile_name]
            if not profiles:
                continue
        # detect_profiles 已把默认 profile 排在最前
        result.append(profiles[0])
    return result


def cmd_list(args: argparse.Namespace) -> int:
    """列出检测到的浏览器与 profile, 不读写本地库。"""
    found = False
    for backend in all_backends():
        profiles = backend.detect_profiles(args.user_data_dir)
        if not profiles:
            continue
        found = True
        print("%s:" % backend.name)
        for index, profile in enumerate(profiles):
            mark = "*" if index == 0 else " "
            print("  %s %-28s %s" % (mark, profile.name, profile.history_path))
    if not found:
        print("没有检测到已安装的浏览器")
        if not is_mac():
            print("(Safari 仅在 macOS 上可用)")
        return 1
    print("\n带 * 的是默认 profile, sync 默认同步它")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    if args.browser and args.browser not in BROWSER_NAMES:
        sys.stderr.write("不支持的浏览器: %s (可选: %s)\n" % (
            args.browser, ", ".join(BROWSER_NAMES)))
        return 2

    profiles = resolve_profiles(args.browser, args.profile, args.user_data_dir)
    if not profiles:
        target = args.browser or "任何浏览器"
        sys.stderr.write("没有检测到 %s 的数据, 可用 `duck-browser list` 查看\n" % target)
        return 1

    store = BrowserStore()
    stats: List[SyncStat] = []
    try:
        for profile in profiles:
            backend = get_backend(profile.browser)
            if backend is None:
                continue
            print("正在同步 %s (%s) ..." % (profile.browser, profile.name))
            try:
                snap = backend.read_snapshot(profile)
                stats.append(store.replace_browser(snap))
            except (BrowserError, sqlite3.Error, OSError) as e:
                # 单个浏览器失败不影响其余
                stats.append(SyncStat(browser=profile.browser, profile=profile.name,
                                      error=str(e)))
    finally:
        store.close()

    print("")
    print_sync_stats(stats)
    return 0 if any(not s.error for s in stats) else 1


def cmd_search(args: argparse.Namespace) -> int:
    keywords = [k for k in args.keywords if k.strip()]
    if not keywords:
        sys.stderr.write("请提供搜索关键词\n")
        return 2
    req = SearchRequest(keywords=keywords, kind=args.type,
                        browser=args.browser, limit=args.limit)
    store = BrowserStore()
    try:
        if store.is_empty():
            sys.stderr.write("本地还没有数据, 请先执行 `duck-browser sync`\n")
            return 1
        hits = store.search(req)
    finally:
        store.close()

    if args.jsonl:
        print_jsonl([h.to_dict() for h in hits])
    else:
        color = {"auto": sys.stdout.isatty(), "always": True, "never": False}[args.color]
        print_search_hits(hits, keywords=keywords, color=color)
    return 0


def cmd_top(args: argparse.Namespace) -> int:
    if args.by not in ("url", "domain"):
        sys.stderr.write("--by 只支持 url 或 domain\n")
        return 2
    req = TopRequest(days=args.days, limit=args.limit, by=args.by,
                     browser=args.browser, all_visits=args.all_visits)
    store = BrowserStore()
    try:
        if store.is_empty():
            sys.stderr.write("本地还没有数据, 请先执行 `duck-browser sync`\n")
            return 1
        rows = store.top(req)
    finally:
        store.close()

    if args.jsonl:
        print_jsonl([r.to_dict() for r in rows])
    else:
        print_top_rows(rows, req)
    return 0


def cmd_stat(args: argparse.Namespace) -> int:
    store = BrowserStore()
    try:
        items = store.stat()
    finally:
        store.close()
    if not items:
        print("本地还没有数据, 请先执行 `duck-browser sync`")
        return 1
    if args.jsonl:
        print_jsonl(items)
        return 0
    # 中文是全角, 用显示宽度而不是字符数对齐
    print("%s %10s %10s %10s  %s" % (
        _pad("浏览器", 10), "书签", "网址", "访问", "上次同步"))
    for item in items:
        print("%s %10d %10d %10d  %s" % (
            _pad(item["browser"], 10), item["bookmarks"], item["urls"],
            item["visits"], unix_to_str(item["last_sync"])))
    print("\n数据库: %s" % store.db_path)
    return 0


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=CMD_NAME,
        description="浏览器书签/历史助手: 同步、搜索与访问统计",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("示例:\n"
                "  duck-browser list                      # 查看检测到的浏览器\n"
                "  duck-browser sync                      # 同步所有已安装浏览器\n"
                "  duck-browser sync -b firefox           # 只同步 Firefox\n"
                "  duck-browser search github issue       # 关键词是 AND 关系\n"
                "  duck-browser top --days 30 --by domain # 30天内访问最多的域名\n"
                "各子命令加 -h 可查看详细参数, 如: duck-browser top -h"))
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser(
        "list", help="列出检测到的浏览器与 profile",
        description="列出本机检测到的浏览器及其 profile, 不读写本地数据库。")
    p_list.add_argument("--user-data-dir", default=None,
                        help="指定浏览器数据目录, 覆盖自动探测")
    p_list.set_defaults(func=cmd_list)

    p_sync = sub.add_parser(
        "sync", help="同步书签与历史到本地库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("把浏览器的书签与历史同步到本地库(全量覆盖)。\n"
                     "同步前会先给浏览器数据库做一致性快照, 因此浏览器开着也能同步。\n"
                     "示例:\n"
                     "  duck-browser sync                # 同步所有已安装浏览器\n"
                     "  duck-browser sync -b chrome      # 只同步 Chrome\n"
                     "  duck-browser sync --profile \"Profile 1\""))
    p_sync.add_argument("-b", "--browser", default=None,
                        help="浏览器: %s (默认全部)" % "|".join(BROWSER_NAMES))
    p_sync.add_argument("--profile", default=None, help="profile 名称 (默认用默认 profile)")
    p_sync.add_argument("--user-data-dir", default=None,
                        help="指定浏览器数据目录, 覆盖自动探测")
    p_sync.set_defaults(func=cmd_sync)

    p_search = sub.add_parser(
        "search", help="模糊搜索书签与历史",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("在本地库里模糊搜索书签与历史, 多个关键词是 AND 关系。\n"
                     "示例:\n"
                     "  duck-browser search github\n"
                     "  duck-browser search github issue    # 同时包含两个词\n"
                     "  duck-browser search 文档 -t bookmark # 只搜书签\n"
                     "  duck-browser search python -n 50 --jsonl"))
    p_search.add_argument("keywords", nargs="+", help="搜索关键词 (匹配标题/网址/书签目录)")
    p_search.add_argument("-t", "--type", default="all",
                          choices=("all", "bookmark", "history"), help="搜索范围")
    p_search.add_argument("-b", "--browser", default=None, help="只搜指定浏览器")
    p_search.add_argument("-n", "--limit", type=int, default=20, help="结果数量 (默认20)")
    p_search.add_argument("--jsonl", action="store_true", help="以 JSONL 输出, 便于管道处理")
    p_search.add_argument("--color", default="auto", choices=("auto", "always", "never"),
                          help="关键词高亮: auto=终端时高亮(默认), always, never")
    p_search.set_defaults(func=cmd_search)

    p_top = sub.add_parser(
        "top", help="统计最近访问最多的页面/域名",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("统计最近一段时间访问最多的页面或域名。\n"
                     "时间窗口是从当前时刻往前推的滚动窗口, 不是自然日。\n"
                     "默认过滤掉重定向与内嵌页面的访问, 加 --all-visits 可统计全部。\n"
                     "示例:\n"
                     "  duck-browser top                     # 最近7天 TOP10 页面\n"
                     "  duck-browser top --days 30 -n 20\n"
                     "  duck-browser top --by domain         # 按域名聚合\n"
                     "  duck-browser top --days 0            # 不限时间"))
    p_top.add_argument("--days", type=int, default=7, help="统计最近几天 (默认7, 0=不限)")
    p_top.add_argument("-n", "--limit", type=int, default=10, help="结果数量 (默认10)")
    p_top.add_argument("--by", default="url", choices=("url", "domain"), help="聚合维度")
    p_top.add_argument("-b", "--browser", default=None, help="只统计指定浏览器")
    p_top.add_argument("--all-visits", action="store_true",
                       help="统计全部访问, 含重定向与内嵌页面")
    p_top.add_argument("--jsonl", action="store_true", help="以 JSONL 输出, 便于管道处理")
    p_top.set_defaults(func=cmd_top)

    p_stat = sub.add_parser(
        "stat", help="查看本地库各浏览器的条目数与上次同步时间",
        description="查看本地库里各浏览器的书签/网址/访问条目数与上次同步时间。")
    p_stat.add_argument("--jsonl", action="store_true", help="以 JSONL 输出")
    p_stat.set_defaults(func=cmd_stat)

    return parser


def main() -> int:
    # -h/--help 必须无副作用, 放在最开头: 后续的 BrowserStore/get_db_path 会创建目录
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        if __doc__ is not None:
            print(__doc__.strip())
        else:
            print("Usage: %s <sync|search|top|list|stat> [options]" % CMD_NAME)
        return 0

    setup_stdout()
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    result = args.func(args)
    return int(result or 0)


if __name__ == "__main__":
    sys.exit(main())
