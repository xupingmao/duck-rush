# -*- coding: utf-8 -*-
"""alias_util(duck-cli 别名机制)单元测试。

直接运行:  python duck_rush/shell/test_duck_alias.py

只依赖标准库。别名文件一律落在临时目录, 不会碰到 ~/.duck-rush 下的真实数据。
"""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
# 优先用工作树里的 duck_utils / alias_util, 避免命中 site-packages 里过期的 egg
sys.path.insert(0, HERE)
sys.path.insert(0, REPO_ROOT)

import alias_util  # noqa: E402 需要先补好 sys.path


class AliasTestCase(unittest.TestCase):
    """每个用例一个独立临时目录 + 固定的默认别名, 与平台无关。"""

    defaults = {"ll": "duck-ls -lh --color"}

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="duck-alias-test-")
        self.path = alias_util.get_default_store_path(self.tmpdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def make_store(self) -> alias_util.AliasStore:
        return alias_util.AliasStore(self.path, defaults=dict(self.defaults))


class TestParseAssign(unittest.TestCase):
    """NAME=CMD 的解析与引号剥离。"""

    def test_double_quotes(self):
        self.assertEqual(alias_util.parse_assign('ll="duck-ls -lh"'),
                         ("ll", "duck-ls -lh"))

    def test_single_quotes(self):
        self.assertEqual(alias_util.parse_assign("gs='git status'"),
                         ("gs", "git status"))

    def test_no_quotes(self):
        self.assertEqual(alias_util.parse_assign("k=duck-ls"), ("k", "duck-ls"))

    def test_inner_quotes_kept(self):
        # 只剥掉最外层成对引号, 内部引号原样保留
        self.assertEqual(alias_util.parse_assign('g="git log --pretty=\'%h\'"'),
                         ("g", "git log --pretty='%h'"))

    def test_not_assignment(self):
        self.assertIsNone(alias_util.parse_assign("ll"))

    def test_empty_name(self):
        self.assertIsNone(alias_util.parse_assign("=duck-ls"))

    def test_format_alias(self):
        self.assertEqual(alias_util.format_alias("ll", "duck-ls -lh"),
                         "alias ll='duck-ls -lh'")


class TestDefaults(unittest.TestCase):
    """内置默认别名。"""

    def test_ll_present(self):
        self.assertEqual(alias_util.DEFAULT_ALIASES.get("ll"),
                         "duck-ls -lh --color")

    def test_ls_only_on_windows(self):
        # Windows 无原生 ls, 才把 ls 指向 duck-ls
        aliases = alias_util.build_default_aliases()
        if os.name == "nt":
            self.assertEqual(aliases.get("ls"), "duck-ls --color")
        else:
            self.assertNotIn("ls", aliases)


class TestExpand(AliasTestCase):
    """别名展开(只作用于首个 token)。"""

    def test_expand_bare(self):
        store = self.make_store()
        self.assertEqual(store.expand("ll"), "duck-ls -lh --color")

    def test_expand_keeps_args(self):
        store = self.make_store()
        self.assertEqual(store.expand("ll /tmp"), "duck-ls -lh --color /tmp")

    def test_unknown_untouched(self):
        store = self.make_store()
        self.assertEqual(store.expand("git status"), "git status")

    def test_only_first_token(self):
        # 别名只在命令名位置生效, 参数里的同名单词不受影响
        store = self.make_store()
        self.assertEqual(store.expand("echo ll"), "echo ll")

    def test_self_reference_terminates(self):
        # bash 语义: 同名别名不二次展开, 不会死循环
        store = self.make_store()
        store.set("ls", "ls -l")
        self.assertEqual(store.expand("ls"), "ls -l")

    def test_chain_expansion(self):
        store = self.make_store()
        store.set("l1", "l2 -a")
        store.set("l2", "duck-ls")
        self.assertEqual(store.expand("l1"), "duck-ls -a")

    def test_mutual_recursion_terminates(self):
        store = self.make_store()
        store.set("a", "b")
        store.set("b", "a")
        # 只要能返回就说明没有死循环
        self.assertIn(store.expand("a"), ("a", "b"))

    def test_blank_input(self):
        store = self.make_store()
        self.assertEqual(store.expand("   "), "   ")

    def test_leading_space(self):
        store = self.make_store()
        self.assertEqual(store.expand("  ll"), "duck-ls -lh --color")


class TestPersistence(AliasTestCase):
    """增删与持久化。"""

    def test_set_then_reload(self):
        store = self.make_store()
        store.set("gs", "git status")
        self.assertEqual(self.make_store().get("gs"), "git status")

    def test_override_default_persists(self):
        store = self.make_store()
        store.set("ll", "duck-ls -la")
        self.assertEqual(self.make_store().get("ll"), "duck-ls -la")

    def test_remove_custom(self):
        store = self.make_store()
        store.set("gs", "git status")
        self.assertTrue(store.remove("gs"))
        self.assertIsNone(self.make_store().get("gs"))

    def test_remove_default_leaves_tombstone(self):
        # 删除内置别名后重启不应该又冒出来
        store = self.make_store()
        self.assertTrue(store.remove("ll"))
        self.assertIsNone(store.get("ll"))
        self.assertIsNone(self.make_store().get("ll"))

    def test_remove_unknown(self):
        self.assertFalse(self.make_store().remove("nope"))

    def test_readd_after_remove(self):
        store = self.make_store()
        store.remove("ll")
        store.set("ll", "duck-ls -1")
        self.assertEqual(self.make_store().get("ll"), "duck-ls -1")

    def test_names_sorted(self):
        store = self.make_store()
        store.set("zz", "x")
        store.set("aa", "y")
        self.assertEqual(store.names(), sorted(store.names()))

    def test_missing_file_is_ok(self):
        # 文件还不存在时只暴露内置别名
        self.assertEqual(self.make_store().all(), self.defaults)

    def test_corrupted_file_is_tolerated(self):
        with open(self.path, "w", encoding="utf-8") as fp:
            fp.write("这不是 json\n")
            fp.write('{"name": "ok", "cmd": "duck-ls"}\n')
        store = self.make_store()
        self.assertEqual(store.get("ok"), "duck-ls")
        self.assertEqual(store.get("ll"), self.defaults["ll"])


class TestInvalidInput(AliasTestCase):
    """非法输入应抛 AliasError 而不是写坏文件。"""

    def test_name_with_space(self):
        store = self.make_store()
        with self.assertRaises(alias_util.AliasError):
            store.set("bad name", "duck-ls")

    def test_name_with_equal(self):
        store = self.make_store()
        with self.assertRaises(alias_util.AliasError):
            store.set("a=b", "duck-ls")

    def test_empty_cmd(self):
        store = self.make_store()
        with self.assertRaises(alias_util.AliasError):
            store.set("x", "   ")


if __name__ == "__main__":
    unittest.main(verbosity=2)
