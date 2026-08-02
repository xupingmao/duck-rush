# -*- coding: utf-8 -*-
"""duck-vocab（命令行生词本）单元测试。

直接运行:  python duck_rush/dict/test_duck_vocab.py

通过 importlib 加载带连字符的脚本模块，用临时数据文件验证
add / update / remove(delete) / list 的核心逻辑，避免污染用户数据。
"""
import argparse
import importlib.util
import os
import tempfile
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "duck-vocab.py")


def load_mod():
    """以 importlib 加载带连字符的脚本模块。"""
    spec = importlib.util.spec_from_file_location("duck_vocab_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestVocab(unittest.TestCase):
    def setUp(self):
        self.m = load_mod()
        # 强制 DAO 指向临时文件, 不污染 ~/.duck-rush
        self.tmp = tempfile.mkdtemp(prefix="duck_vocab_")
        self.m._dao = self.m.VocabDao(os.path.join(self.tmp, "vocab.jsonl"))

    def _run(self, argv):
        parser = self.m.build_parser()
        args = parser.parse_args(argv)
        args.func(args)

    def test_add_then_list(self):
        self._run(["add", "hello", "-m", "你好", "-t", "greeting"])
        items = self.m.get_dao().list_all()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].word, "hello")
        self.assertEqual(items[0].tags, ["greeting"])

    def test_update_partial_keeps_other_fields(self):
        self._run(["add", "hello", "-m", "你好", "-e", "say hello", "-t", "greeting"])
        # 仅更新释义与标签, 例句应保持不变
        self._run(["update", "1", "-m", "你好(更新)", "-t", "g1,g2"])
        e = self.m.get_dao().get_by_id(1)
        self.assertEqual(e.meaning, "你好(更新)")
        self.assertEqual(e.tags, ["g1", "g2"])
        self.assertEqual(e.example, "say hello")  # 未改, 保留
        self.assertEqual(e.word, "hello")          # 未改, 保留

    def test_update_empty_word_rejected(self):
        self._run(["add", "hello", "-m", "你好"])
        with self.assertRaises(SystemExit):
            self._run(["update", "1", "-w", "   "])

    def test_update_missing_id(self):
        self._run(["add", "hello"])
        # ID=99 不存在, update 应返回 None 并打印未找到, 不抛异常
        self._run(["update", "99", "-m", "x"])
        self.assertEqual(len(self.m.get_dao().list_all()), 1)

    def test_remove_with_yes(self):
        self._run(["add", "hello"])
        self._run(["remove", "1", "-y"])
        self.assertEqual(self.m.get_dao().list_all(), [])

    def test_remove_without_yes_cancels_in_noninteractive(self):
        self._run(["add", "hello"])
        # 非交互 (stdin 非终端) 时未确认, 应保留记录且不阻塞
        self._run(["remove", "1"])
        self.assertEqual(len(self.m.get_dao().list_all()), 1)

    def test_delete_alias(self):
        self._run(["add", "hello"])
        self._run(["add", "world"])
        self._run(["delete", "2", "-y"])
        items = self.m.get_dao().list_all()
        self.assertEqual([e.word for e in items], ["hello"])

    def test_remove_missing_id(self):
        self._run(["remove", "42", "-y"])
        self.assertEqual(self.m.get_dao().list_all(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
