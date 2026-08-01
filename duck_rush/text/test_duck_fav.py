# -*- coding: utf-8 -*-
"""duck-fav（文件收藏夹 CLI）单元测试。

内部函数（增删查 / 去重）通过 importlib 直接加载模块测试;
CLI 行为（主要是 -h 无副作用）通过子进程运行 duck-fav.py 做端到端验证。
"""

import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "duck-fav.py")


def load_mod():
    """以 importlib 加载带连字符的脚本模块。"""
    spec = importlib.util.spec_from_file_location("duck_fav_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFav(unittest.TestCase):
    """直接测试增删查逻辑（数据目录被替换为临时目录，避免污染真实环境）。"""

    def setUp(self):
        self.m = load_mod()
        self.tmp = tempfile.mkdtemp(prefix="duck_fav_")
        # 把命令数据目录重定向到临时目录
        self.m.get_command_data_dir = lambda cmd: self.tmp
        self.store = self.m._store()

    def _touch(self, name):
        p = os.path.join(self.tmp, name)
        with open(p, "w", encoding="utf-8") as fp:
            fp.write("x")
        return p

    def test_add_and_dedup(self):
        a = self._touch("a.txt")
        b = self._touch("b.txt")
        self.m.cmd_add(self.store, [a, b])
        self.assertEqual(len(self.store.read_all()), 2)
        # 重复添加应被去重
        self.m.cmd_add(self.store, [a])
        self.assertEqual(len(self.store.read_all()), 2)

    def test_list_outputs_paths(self):
        a = self._touch("a.txt")
        self.m.cmd_add(self.store, [a])
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.m.cmd_list(self.store)
        self.assertIn(a, buf.getvalue())

    def test_rm_removes(self):
        a = self._touch("a.txt")
        b = self._touch("b.txt")
        self.m.cmd_add(self.store, [a, b])
        self.m.cmd_rm(self.store, [a])
        remaining = self.m._all_paths(self.store)
        self.assertEqual(remaining, [b])

    def test_rm_missing_is_noop(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = self.m.cmd_rm(self.store, ["/no/such/file"])
        self.assertEqual(rc, 0)
        self.assertIn("未找到", out.getvalue())

    def test_clear_with_yes(self):
        a = self._touch("a.txt")
        self.m.cmd_add(self.store, [a])
        self.m.cmd_clear(self.store, yes=True)
        self.assertEqual(self.store.read_all(), [])

    def test_paths_stored_as_absolute(self):
        a = self._touch("a.txt")
        self.m.cmd_add(self.store, [a])
        rec = self.store.read_all()[0]
        self.assertTrue(os.path.isabs(rec["path"]))


class TestSelect(unittest.TestCase):
    """测试 select 子命令（TUI 本身需真实终端，这里只测协议与分类逻辑）。"""

    def setUp(self):
        self.m = load_mod()
        self.tmp = tempfile.mkdtemp(prefix="duck_fav_sel_")
        self.m.get_command_data_dir = lambda cmd: self.tmp
        self.store = self.m._store()

    def _mk(self, name, is_dir=False):
        p = os.path.join(self.tmp, name)
        if is_dir:
            os.makedirs(p, exist_ok=True)
        else:
            with open(p, "w", encoding="utf-8") as fp:
                fp.write("x")
        return p

    def test_empty_store_writes_exit(self):
        # 无收藏时不应启动 TUI，直接输出 exit
        rf = os.path.join(self.tmp, "result.txt")
        rc = self.m.cmd_select(self.store, result_file=rf)
        self.assertEqual(rc, 0)
        with open(rf, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "exit")

    def test_build_entries_classifies(self):
        d = self._mk("sub", is_dir=True)
        f = self._mk("a.txt")
        # 不构造真实 Application（测试环境无 TTY）
        self.m.FavSelectApp._build = lambda self: None
        app = self.m.FavSelectApp([d, f])
        self.assertEqual(app.entries[0].kind, "dir")
        self.assertEqual(app.entries[1].kind, "file")
        self.assertFalse(app.entries[0].missing)
        # 不存在的路径标记 missing
        app2 = self.m.FavSelectApp(["/no/such/path/xyz"])
        self.assertTrue(app2.entries[0].missing)

    def test_act_emits_dir_and_file(self):
        self.m.FavSelectApp._build = lambda self: None
        app = self.m.FavSelectApp([])
        app.entries = [
            self.m.FavEntry("/tmp/d", "dir", False),
            self.m.FavEntry("/tmp/f", "file", False),
        ]
        app.index = 0
        app._act(app.entries[0])
        self.assertEqual(app.result, "dir /tmp/d")
        app.index = 1
        app._act(app.entries[1])
        self.assertEqual(app.result, "file /tmp/f")


class TestCLI(unittest.TestCase):
    """端到端验证命令行行为（重点：-h 必须无副作用）。"""

    def test_help_no_side_effect(self):
        # -h 应在解析任何子命令前退出，绝不触碰数据文件
        real_dir = None
        try:
            import duck_utils.os_util as ou
            real_dir = ou.get_command_data_dir("duck-fav")
        except Exception:
            real_dir = None
        target = os.path.join(real_dir, "bookmarks.jsonl") if real_dir else None
        before = os.path.exists(target) if target else False

        proc = subprocess.run(
            [sys.executable, SCRIPT, "-h"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("duck-fav", proc.stdout)

        after = os.path.exists(target) if target else False
        if not before:
            self.assertFalse(after, "-h 不应创建数据文件")

    def test_select_help_no_side_effect(self):
        # `duck-fav select -h` 也应无副作用（不启动 TUI、不读写数据文件）
        real_dir = None
        try:
            import duck_utils.os_util as ou
            real_dir = ou.get_command_data_dir("duck-fav")
        except Exception:
            real_dir = None
        target = os.path.join(real_dir, "bookmarks.jsonl") if real_dir else None
        before = os.path.exists(target) if target else False

        proc = subprocess.run(
            [sys.executable, SCRIPT, "select", "-h"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("select", proc.stdout.lower())

        after = os.path.exists(target) if target else False
        if not before:
            self.assertFalse(after, "select -h 不应创建数据文件")


if __name__ == "__main__":
    unittest.main(verbosity=2)
