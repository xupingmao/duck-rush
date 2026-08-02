# -*- coding: utf-8 -*-
"""duck-browser 单元测试。

直接运行:  python duck_rush/os/test_duck_browser.py

在临时目录里造出假的 Chromium / Firefox profile 做端到端验证, 不触碰真实浏览器数据,
也不写入真实的 ~/.duck-rush 目录。
"""

import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "duck-browser.py")
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))

CHROME_EPOCH_DIFF = 11644473600.0
DAY = 86400.0


def load_mod() -> types.ModuleType:
    """以 importlib 加载带连字符的脚本模块。"""
    spec = importlib.util.spec_from_file_location("duck_browser_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def to_chrome_time(unix_ts: float) -> int:
    return int((unix_ts + CHROME_EPOCH_DIFF) * 1e6)


def to_firefox_time(unix_ts: float) -> int:
    return int(unix_ts * 1e6)


# ---------------------------------------------------------------------------
# 假 profile 构造
# ---------------------------------------------------------------------------
def make_chromium_profile(root: str) -> str:
    """在 root 下造 User Data/Default/{History,Bookmarks}, 返回 user_data_dir。"""
    user_data_dir = os.path.join(root, "User Data")
    profile_dir = os.path.join(user_data_dir, "Default")
    os.makedirs(profile_dir, exist_ok=True)

    now = time.time()
    conn = sqlite3.connect(os.path.join(profile_dir, "History"))
    conn.executescript("""
        CREATE TABLE urls(id INTEGER PRIMARY KEY AUTOINCREMENT, url LONGVARCHAR,
            title LONGVARCHAR, visit_count INTEGER DEFAULT 0 NOT NULL,
            typed_count INTEGER DEFAULT 0 NOT NULL, last_visit_time INTEGER NOT NULL,
            hidden INTEGER DEFAULT 0 NOT NULL);
        CREATE TABLE visits(id INTEGER PRIMARY KEY AUTOINCREMENT, url INTEGER NOT NULL,
            visit_time INTEGER NOT NULL, from_visit INTEGER,
            transition INTEGER DEFAULT 0 NOT NULL, visit_duration INTEGER DEFAULT 0 NOT NULL);
    """)
    urls = [
        # id, url, title, visit_count, typed, last_visit(天前), hidden
        (1, "https://github.com/foo/bar", "GITHUB Issue Tracker", 5, 1, 1.0, 0),
        (2, "https://github.com/baz/qux", "Café Pull Request", 3, 0, 2.0, 0),
        (3, "https://example.com/old", "Old Page", 9, 0, 10.0, 0),
        (4, "https://example.com/sale", "100% pure discount", 1, 0, 1.0, 0),
        (5, "https://hidden.example.com/x", "Hidden Page", 7, 0, 1.0, 1),
    ]
    for uid, url, title, vc, tc, days_ago, hidden in urls:
        conn.execute("INSERT INTO urls VALUES (?,?,?,?,?,?,?)",
                     (uid, url, title, vc, tc,
                      to_chrome_time(now - days_ago * DAY), hidden))
    visits = [
        # url_id, 天前, transition
        (1, 1.0, 0), (1, 1.1, 0), (1, 1.2, 0),           # 3 次正常
        (1, 1.3, 0x80000000),                              # 1 次重定向
        (2, 2.0, 0), (2, 2.1, 0),                          # 2 次正常
        (3, 10.0, 0), (3, 10.1, 0), (3, 10.2, 0), (3, 10.3, 0),  # 4 次但在窗口外
        (4, 1.0, 0),
        (5, 1.0, 0),                                       # hidden 的 url, 应被排除
    ]
    for url_id, days_ago, transition in visits:
        conn.execute("INSERT INTO visits (url, visit_time, transition) VALUES (?,?,?)",
                     (url_id, to_chrome_time(now - days_ago * DAY), transition))
    conn.commit()
    conn.close()

    bookmarks = {
        "version": 1,
        "checksum": "fake",
        # roots 里混有字符串值的兄弟键, 遍历时必须能跳过
        "sync_transaction_version": "1",
        "roots": {
            "bookmark_bar": {
                "type": "folder", "name": "书签栏", "date_added": "0",
                "children": [
                    {"type": "url", "name": "GitHub 文档", "guid": "g1",
                     "url": "https://docs.github.com",
                     "date_added": str(to_chrome_time(now - 30 * DAY))},
                    {"type": "folder", "name": "技术", "children": [
                        {"type": "url", "name": "Python 文档", "guid": "g2",
                         "url": "https://docs.python.org",
                         "date_added": str(to_chrome_time(now - 20 * DAY))},
                    ]},
                    # date_added 为 "0" 的边界: 不能算出 1601 年
                    {"type": "url", "name": "无日期书签", "guid": "g3",
                     "url": "https://no-date.example.com", "date_added": "0"},
                ],
            },
            "other": {"type": "folder", "name": "其他书签", "children": []},
        },
    }
    with open(os.path.join(profile_dir, "Bookmarks"), "w", encoding="utf-8") as f:
        json.dump(bookmarks, f, ensure_ascii=False)
    return user_data_dir


def make_firefox_profile(root: str) -> str:
    """在 root 下造 Firefox 目录(含 profiles.ini 与两个 profile), 返回 firefox_dir。

    刻意复刻实测中的陷阱: [Profile1] Default=1 指向空 profile,
    而 [Install] 段指向真正在用的那个。
    """
    firefox_dir = os.path.join(root, "Firefox")
    real_rel = "Profiles/aaaa.default-release"
    empty_rel = "Profiles/bbbb.default"
    real_dir = os.path.join(firefox_dir, "Profiles", "aaaa.default-release")
    empty_dir = os.path.join(firefox_dir, "Profiles", "bbbb.default")
    os.makedirs(real_dir, exist_ok=True)
    os.makedirs(empty_dir, exist_ok=True)

    with open(os.path.join(firefox_dir, "profiles.ini"), "w", encoding="utf-8") as f:
        f.write("[Install1234]\nDefault=%s\nLocked=1\n\n" % real_rel)
        f.write("[Profile1]\nName=default\nIsRelative=1\nPath=%s\nDefault=1\n\n" % empty_rel)
        f.write("[Profile0]\nName=default-release\nIsRelative=1\nPath=%s\n\n" % real_rel)
        f.write("[General]\nStartWithLastProfile=1\nVersion=2\n")

    now = time.time()
    for target, with_data in ((real_dir, True), (empty_dir, False)):
        conn = sqlite3.connect(os.path.join(target, "places.sqlite"))
        conn.executescript("""
            CREATE TABLE moz_places(id INTEGER PRIMARY KEY, url LONGVARCHAR,
                title LONGVARCHAR, visit_count INTEGER DEFAULT 0,
                hidden INTEGER DEFAULT 0 NOT NULL, typed INTEGER DEFAULT 0 NOT NULL,
                last_visit_date INTEGER, guid TEXT);
            CREATE TABLE moz_historyvisits(id INTEGER PRIMARY KEY, from_visit INTEGER,
                place_id INTEGER, visit_date INTEGER, visit_type INTEGER);
            CREATE TABLE moz_bookmarks(id INTEGER PRIMARY KEY, type INTEGER,
                fk INTEGER DEFAULT NULL, parent INTEGER, position INTEGER,
                title LONGVARCHAR, dateAdded INTEGER, guid TEXT);
        """)
        if with_data:
            conn.execute(
                "INSERT INTO moz_places VALUES (1,'https://mozilla.org','Mozilla 首页',"
                "4,0,0,?,'p1')", (to_firefox_time(now - 1 * DAY),))
            conn.execute(
                "INSERT INTO moz_places VALUES (2,'https://hidden.org','Hidden',"
                "2,1,0,?,'p2')", (to_firefox_time(now - 1 * DAY),))
            for days_ago, vtype in ((1.0, 1), (1.1, 1), (1.2, 5)):
                conn.execute("INSERT INTO moz_historyvisits "
                             "(place_id, visit_date, visit_type) VALUES (1,?,?)",
                             (to_firefox_time(now - days_ago * DAY), vtype))
            conn.execute("INSERT INTO moz_historyvisits "
                         "(place_id, visit_date, visit_type) VALUES (2,?,1)",
                         (to_firefox_time(now - 1 * DAY),))
            conn.execute("INSERT INTO moz_bookmarks VALUES "
                         "(1,2,NULL,0,0,'',0,'root________')")
            conn.execute("INSERT INTO moz_bookmarks VALUES "
                         "(3,2,NULL,1,0,'toolbar',0,'toolbar_____')")
            conn.execute("INSERT INTO moz_bookmarks VALUES (10,2,NULL,3,0,'开发',0,'f10')")
            conn.execute("INSERT INTO moz_bookmarks VALUES (11,1,1,10,0,'Mozilla 书签',?,'b11')",
                         (to_firefox_time(now - 5 * DAY),))
        conn.commit()
        conn.close()
    return firefox_dir


# ---------------------------------------------------------------------------
# 纯函数
# ---------------------------------------------------------------------------
class TestHelpers(unittest.TestCase):
    """时间换算、域名、LIKE 转义等纯函数"""

    def setUp(self) -> None:
        self.m = load_mod()

    def test_chrome_time_boundary(self) -> None:
        # 空值/零值/非法值一律 0.0, 不能算出 1601 年的负数时间
        for bad in (None, "", "0", 0, "abc", -1):
            self.assertEqual(self.m.to_unix_time(bad, CHROME_EPOCH_DIFF), 0.0,
                             "输入 %r 应返回 0.0" % (bad,))
        now = 1700000000.0
        got = self.m.to_unix_time(to_chrome_time(now), CHROME_EPOCH_DIFF)
        self.assertAlmostEqual(got, now, places=3)

    def test_firefox_time(self) -> None:
        now = 1700000000.0
        got = self.m.to_unix_time(to_firefox_time(now), 0.0)
        self.assertAlmostEqual(got, now, places=3)

    def test_get_domain(self) -> None:
        self.assertEqual(self.m.get_domain("https://Example.COM:8080/a?b=1"),
                         "example.com")
        self.assertEqual(self.m.get_domain("not a url"), "")

    def test_like_pattern_escapes(self) -> None:
        self.assertEqual(self.m.like_pattern("100%"), "%100\\%%")
        self.assertEqual(self.m.like_pattern("a_b"), "%a\\_b%")
        self.assertEqual(self.m.like_pattern("C:\\x"), "%c:\\\\x%")

    def test_build_search_text_unicode_lower(self) -> None:
        # Python 的 lower() 是 Unicode 感知的, SQLite 的 LOWER() 只折叠 ASCII
        self.assertEqual(self.m.build_search_text("CAFÉ", "GitHub"), "café github")

    def test_disp_width_and_pad(self) -> None:
        self.assertEqual(self.m._disp_width("中文"), 4)
        self.assertEqual(self.m._disp_width("ab"), 2)
        self.assertEqual(len(self.m._pad("中文", 10)), 2 + 6)


# ---------------------------------------------------------------------------
# 快照
# ---------------------------------------------------------------------------
class TestSnapshot(unittest.TestCase):
    """DbSnapshot 的一致性与清理"""

    def setUp(self) -> None:
        self.m = load_mod()
        self.tmp = tempfile.mkdtemp(prefix="duck_browser_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_reads_uncheckpointed_wal(self) -> None:
        """源库处于 WAL 且未 checkpoint 时, 快照仍要能读到最新数据。"""
        db_path = os.path.join(self.tmp, "src.db")
        holder = sqlite3.connect(db_path)
        holder.execute("PRAGMA journal_mode=WAL")
        holder.execute("CREATE TABLE t(x int)")
        holder.execute("INSERT INTO t VALUES (42)")
        holder.commit()
        # 保持连接不关闭, 模拟浏览器正在运行
        try:
            with self.m.DbSnapshot(db_path) as conn:
                self.assertEqual(conn.execute("SELECT x FROM t").fetchone()[0], 42)
        finally:
            holder.close()

    def test_cleans_tempdir(self) -> None:
        db_path = os.path.join(self.tmp, "src.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t(x int)")
        conn.commit()
        conn.close()

        snap = self.m.DbSnapshot(db_path)
        with snap:
            tmp_dir = snap.tmp_dir
            self.assertTrue(os.path.isdir(tmp_dir))
        # Windows 上连接没关就删目录会报 WinError 32
        self.assertFalse(os.path.exists(tmp_dir))

    def test_missing_db_raises(self) -> None:
        with self.assertRaises(self.m.BrowserError):
            with self.m.DbSnapshot(os.path.join(self.tmp, "nope.db")):
                pass


# ---------------------------------------------------------------------------
# 浏览器后端
# ---------------------------------------------------------------------------
class TestBackends(unittest.TestCase):
    """profile 探测与数据读取"""

    def setUp(self) -> None:
        self.m = load_mod()
        self.tmp = tempfile.mkdtemp(prefix="duck_browser_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.chromium_dir = make_chromium_profile(os.path.join(self.tmp, "chrome"))
        self.firefox_dir = make_firefox_profile(os.path.join(self.tmp, "ff"))

    def _chromium(self):
        return self.m.ChromiumBackend("chrome", "x", "x", "x")

    def test_chromium_reads_bookmarks(self) -> None:
        backend = self._chromium()
        profile = backend.detect_profiles(self.chromium_dir)[0]
        snap = backend.read_snapshot(profile)
        by_name = {b.name: b for b in snap.bookmarks}
        self.assertEqual(set(by_name), {"GitHub 文档", "Python 文档", "无日期书签"})
        # 文件夹路径要逐层拼出来
        self.assertEqual(by_name["Python 文档"].folder, "书签栏/技术")
        self.assertEqual(by_name["GitHub 文档"].folder, "书签栏")
        # date_added="0" 不能变成 1601 年
        self.assertEqual(by_name["无日期书签"].date_added, 0.0)
        self.assertGreater(by_name["GitHub 文档"].date_added, 0)

    def test_chromium_skips_hidden_urls(self) -> None:
        backend = self._chromium()
        profile = backend.detect_profiles(self.chromium_dir)[0]
        snap = backend.read_snapshot(profile)
        urls = {u.url for u in snap.urls}
        self.assertNotIn("https://hidden.example.com/x", urls)
        self.assertEqual(len(urls), 4)

    def test_chromium_marks_redirect(self) -> None:
        backend = self._chromium()
        profile = backend.detect_profiles(self.chromium_dir)[0]
        snap = backend.read_snapshot(profile)
        rows = list(snap.visit_rows)
        redirects = [r for r in rows if r[3] == 1]
        self.assertEqual(len(redirects), 1)
        # hidden 的 url 对应的访问也要被排除
        self.assertEqual(len(rows), 11)

    def test_firefox_prefers_install_default_profile(self) -> None:
        """[Install] 段指向的 profile 要排在 Default=1 之前。"""
        backend = self.m.FirefoxBackend()
        profiles = backend.detect_profiles(self.firefox_dir)
        self.assertEqual(len(profiles), 2)
        self.assertEqual(profiles[0].name, "default-release")

    def test_firefox_reads_data(self) -> None:
        backend = self.m.FirefoxBackend()
        profile = backend.detect_profiles(self.firefox_dir)[0]
        snap = backend.read_snapshot(profile)
        self.assertEqual([u.url for u in snap.urls], ["https://mozilla.org"])
        self.assertEqual([b.name for b in snap.bookmarks], ["Mozilla 书签"])
        # 根文件夹 toolbar 换成中文, 且路径自底向上拼好
        self.assertEqual(snap.bookmarks[0].folder, "书签栏/开发")
        rows = list(snap.visit_rows)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len([r for r in rows if r[3] == 1]), 1)

    def test_detect_returns_empty_when_absent(self) -> None:
        missing = os.path.join(self.tmp, "not-exists")
        self.assertEqual(self._chromium().detect_profiles(missing), [])
        self.assertEqual(self.m.FirefoxBackend().detect_profiles(missing), [])


# ---------------------------------------------------------------------------
# 存储层
# ---------------------------------------------------------------------------
class TestStore(unittest.TestCase):
    """同步、搜索、统计"""

    def setUp(self) -> None:
        self.m = load_mod()
        self.tmp = tempfile.mkdtemp(prefix="duck_browser_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.chromium_dir = make_chromium_profile(os.path.join(self.tmp, "chrome"))
        self.firefox_dir = make_firefox_profile(os.path.join(self.tmp, "ff"))
        self.store = self.m.BrowserStore(db_path=os.path.join(self.tmp, "test.db"))
        self.addCleanup(self.store.close)

    def _sync_chromium(self, name: str = "chrome"):
        backend = self.m.ChromiumBackend(name, "x", "x", "x")
        profile = backend.detect_profiles(self.chromium_dir)[0]
        return self.store.replace_browser(backend.read_snapshot(profile))

    def _sync_firefox(self):
        backend = self.m.FirefoxBackend()
        profile = backend.detect_profiles(self.firefox_dir)[0]
        return self.store.replace_browser(backend.read_snapshot(profile))

    def test_get_db_path_uses_command_data_dir(self) -> None:
        """数据目录必须来自 get_command_data_dir, 不能散落到别处。"""
        self.m.get_command_data_dir = lambda cmd: self.tmp
        self.assertEqual(self.m.get_db_path(), os.path.join(self.tmp, "browser.db"))

    def test_sync_counts(self) -> None:
        stat = self._sync_chromium()
        self.assertEqual(stat.bookmarks, 3)
        self.assertEqual(stat.urls, 4)
        self.assertEqual(stat.visits, 11)

    def test_sync_is_idempotent(self) -> None:
        first = self._sync_chromium()
        second = self._sync_chromium()
        self.assertEqual((first.bookmarks, first.urls, first.visits),
                         (second.bookmarks, second.urls, second.visits))
        row = self.store.conn.execute("SELECT COUNT(1) FROM urls").fetchone()
        self.assertEqual(int(row[0]), 4)

    def test_sync_isolates_browsers(self) -> None:
        """重同步一个浏览器不能清掉其他浏览器的数据。"""
        self._sync_chromium("chrome")
        self._sync_firefox()
        self._sync_chromium("chrome")
        rows = self.store.conn.execute(
            "SELECT browser, COUNT(1) FROM urls GROUP BY browser").fetchall()
        counts = {r[0]: r[1] for r in rows}
        self.assertEqual(counts, {"chrome": 4, "firefox": 1})

    def test_sync_rolls_back_on_error(self) -> None:
        """中途失败要回滚, 旧数据必须完好。"""
        self._sync_chromium()
        before = self.store.conn.execute("SELECT COUNT(1) FROM urls").fetchone()[0]

        def boom():
            yield ("chrome", 1, time.time(), 0)
            raise RuntimeError("模拟读取中断")

        bad = self.m.BrowserSnapshot(browser="chrome", profile="Default")
        bad.visit_rows = boom()
        with self.assertRaises(RuntimeError):
            self.store.replace_browser(bad)
        after = self.store.conn.execute("SELECT COUNT(1) FROM urls").fetchone()[0]
        self.assertEqual(after, before)

    def test_search_multi_keyword_is_and(self) -> None:
        self._sync_chromium()
        req = self.m.SearchRequest(keywords=["github", "issue"])
        hits = self.store.search(req)
        self.assertEqual([h.url for h in hits], ["https://github.com/foo/bar"])

    def test_search_escapes_wildcards(self) -> None:
        """搜 100% 不能因为 % 是通配符而匹配到全部记录。"""
        self._sync_chromium()
        hits = self.store.search(self.m.SearchRequest(keywords=["100%"]))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].url, "https://example.com/sale")

    def test_search_unicode_case_insensitive(self) -> None:
        """SQLite 的 LIKE 只折叠 ASCII, 非 ASCII 要靠预降写的 search_text。"""
        self._sync_chromium()
        self.assertTrue(self.store.search(self.m.SearchRequest(keywords=["GITHUB"])))
        hits = self.store.search(self.m.SearchRequest(keywords=["CAFÉ"]))
        self.assertEqual([h.url for h in hits], ["https://github.com/baz/qux"])

    def test_search_filters_by_kind_and_browser(self) -> None:
        self._sync_chromium()
        self._sync_firefox()
        hits = self.store.search(self.m.SearchRequest(keywords=["文档"], kind="bookmark"))
        self.assertTrue(hits)
        self.assertTrue(all(h.kind == "bookmark" for h in hits))
        hits = self.store.search(self.m.SearchRequest(keywords=["mozilla"],
                                                      browser="firefox"))
        self.assertTrue(hits)
        self.assertTrue(all(h.browser == "firefox" for h in hits))

    def test_top_respects_days_window(self) -> None:
        self._sync_chromium()
        rows = self.store.top(self.m.TopRequest(days=7))
        keys = [r.key for r in rows]
        # 10 天前的页面虽然访问次数更多, 也要被 7 天窗口排除
        self.assertNotIn("https://example.com/old", keys)
        rows_all = self.store.top(self.m.TopRequest(days=0))
        self.assertIn("https://example.com/old", [r.key for r in rows_all])

    def test_top_excludes_redirect_by_default(self) -> None:
        self._sync_chromium()
        rows = self.store.top(self.m.TopRequest(days=7))
        top = {r.key: r.visits for r in rows}
        self.assertEqual(top["https://github.com/foo/bar"], 3)
        rows = self.store.top(self.m.TopRequest(days=7, all_visits=True))
        top = {r.key: r.visits for r in rows}
        self.assertEqual(top["https://github.com/foo/bar"], 4)

    def test_top_by_domain_aggregates(self) -> None:
        self._sync_chromium()
        rows = self.store.top(self.m.TopRequest(days=7, by="domain"))
        by_key = {r.key: r for r in rows}
        # github.com 下两个页面合并: 3 + 2 次访问
        self.assertEqual(by_key["github.com"].visits, 5)
        self.assertEqual(by_key["github.com"].urls, 2)

    def test_top_limit(self) -> None:
        self._sync_chromium()
        self.assertEqual(len(self.store.top(self.m.TopRequest(days=0, limit=2))), 2)

    def test_stat(self) -> None:
        self._sync_chromium()
        items = {i["browser"]: i for i in self.store.stat()}
        self.assertEqual(set(items), {"chrome"})
        self.assertEqual(items["chrome"]["urls"], 4)
        self.assertGreater(items["chrome"]["last_sync"], 0)


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------
class TestCLI(unittest.TestCase):
    """端到端验证命令行行为 (重点: -h 必须无副作用)"""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="duck_browser_cli_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home, exist_ok=True)

    def _env(self) -> dict:
        env = dict(os.environ)
        # 把 HOME 指向临时目录, 避免污染真实的 ~/.duck-rush
        env["HOME"] = self.home
        env["USERPROFILE"] = self.home
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
        return env

    def _run(self, args: list) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, SCRIPT] + args,
                              capture_output=True, text=True,
                              encoding="utf-8", env=self._env(), timeout=120)

    def test_help_no_side_effect(self) -> None:
        """-h 必须在做任何事之前退出, 不能创建数据目录。"""
        for flag in ("-h", "--help"):
            proc = self._run([flag])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("duck-browser", proc.stdout)
            self.assertFalse(
                os.path.exists(os.path.join(self.home, ".duck-rush")),
                "%s 不应创建 ~/.duck-rush 目录" % flag)

    def test_help_first_line_is_brief(self) -> None:
        """install.py 取 -h 首个非空行作为 duck list 的简介。"""
        proc = self._run(["-h"])
        lines = [x.strip() for x in proc.stdout.splitlines() if x.strip()]
        self.assertTrue(lines)
        desc = lines[0]
        self.assertFalse(desc.startswith("usage:"))
        self.assertIn("duck-browser", desc)
        self.assertLess(len(desc), 120)

    def test_list_no_side_effect(self) -> None:
        """list 只探测浏览器, 不应创建本地库。"""
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty, exist_ok=True)
        proc = self._run(["list", "--user-data-dir", empty])
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".duck-rush")))

    def test_end_to_end(self) -> None:
        """sync -> search -> top -> stat 的完整流程。"""
        user_data_dir = make_chromium_profile(os.path.join(self.tmp, "chrome"))

        proc = self._run(["sync", "-b", "chrome", "--user-data-dir", user_data_dir])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("同步完成", proc.stdout)

        proc = self._run(["search", "github", "--jsonl"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = [json.loads(x) for x in proc.stdout.splitlines() if x.strip()]
        self.assertTrue(rows)
        self.assertTrue(all("github" in r["url"].lower() or
                            "github" in r["title"].lower() for r in rows))

        proc = self._run(["top", "--days", "7", "--jsonl"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = [json.loads(x) for x in proc.stdout.splitlines() if x.strip()]
        self.assertTrue(rows)
        self.assertEqual(rows[0]["key"], "https://github.com/foo/bar")
        self.assertEqual(rows[0]["visits"], 3)

        proc = self._run(["stat", "--jsonl"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = [json.loads(x) for x in proc.stdout.splitlines() if x.strip()]
        self.assertEqual(rows[0]["browser"], "chrome")
        self.assertEqual(rows[0]["urls"], 4)

    def test_search_without_sync_hints(self) -> None:
        proc = self._run(["search", "anything"])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("sync", proc.stderr)

    def test_unknown_browser_rejected(self) -> None:
        proc = self._run(["sync", "-b", "netscape"])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("不支持的浏览器", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
