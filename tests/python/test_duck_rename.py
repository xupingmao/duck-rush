#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""duck-rename 日期前缀命令的测试 (add 幂等 / remove 兜底, 不真实改动仓库文件)

运行: python tests/python/test_duck_rename.py
"""
import importlib.util
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
MODULE_PATH = os.path.join(PROJECT_ROOT, "duck_rush", "fs", "duck-rename.py")

# 优先使用仓库内的 duck_utils, 避免命中 site-packages 里的旧拷贝
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

spec = importlib.util.spec_from_file_location("duck_rename", MODULE_PATH)
assert spec is not None and spec.loader is not None
duck_rename = importlib.util.module_from_spec(spec)
spec.loader.exec_module(duck_rename)


class DatePrefixCommandTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def create(self, name):
        fpath = os.path.join(self.tmpdir, name)
        with open(fpath, "w", encoding="utf-8") as fp:
            fp.write("x")
        return fpath

    def add_mapper(self, date_format="%Y%m%d", sep="_"):
        return duck_rename.build_add_date_mapper(date_format, sep)

    def remove_mapper(self, date_format="%Y%m%d", sep="_"):
        return duck_rename.build_remove_date_mapper(date_format, sep)

    def test_add_for_plain_name(self):
        fpath = self.create("report.txt")
        new_name = self.add_mapper()(fpath)
        self.assertRegex(new_name, r"^\d{8}_report\.txt$")

    def test_add_is_idempotent_same_format(self):
        fpath = self.create("20260911_report.txt")
        self.assertEqual(self.add_mapper()(fpath), "20260911_report.txt")

    def test_add_is_idempotent_other_formats(self):
        # 换成 %Y%m%d 后, 旧格式的前缀不应被重复叠加
        for name in ("2026-09-11_report.txt",
                     "2026_09_11_report.txt",
                     "2026.09.11_report.txt",
                     "2026-09-11_123000_report.txt"):
            fpath = self.create(name)
            self.assertEqual(self.add_mapper()(fpath), name,
                             "%s 不应被再次加前缀" % name)

    def test_add_uses_configured_format(self):
        fpath = self.create("report.txt")
        mapper = self.add_mapper(date_format="%Y-%m-%d", sep="-")
        self.assertRegex(mapper(fpath), r"^\d{4}-\d{2}-\d{2}-report\.txt$")

    def test_remove_by_configured_format(self):
        fpath = self.create("20260911_report.txt")
        self.assertEqual(self.remove_mapper()(fpath), "report.txt")

    def test_remove_fallback_other_formats(self):
        cases = {
            "2026-09-11_report.txt": "report.txt",
            "2026_09_11_report.txt": "report.txt",
            "2026.09.11_report.txt": "report.txt",
            "2026-09-11_123000_report.txt": "report.txt",
        }
        for name, expected in cases.items():
            fpath = self.create(name)
            self.assertEqual(self.remove_mapper()(fpath), expected)

    def reformat_mapper(self, date_format="%Y%m%d", sep="_"):
        return duck_rename.build_reformat_date_mapper(date_format, sep)

    def test_reformat_other_formats(self):
        cases = {
            "2026-09-11_report.txt": "20260911_report.txt",
            "2026_09_11_report.txt": "20260911_report.txt",
            "2026.09.11_report.txt": "20260911_report.txt",
            "2026-09-11_123000_report.txt": "20260911_123000_report.txt",
        }
        for name, expected in cases.items():
            fpath = self.create(name)
            self.assertEqual(self.reformat_mapper()(fpath), expected)

    def test_reformat_is_idempotent(self):
        fpath = self.create("20260911_report.txt")
        self.assertEqual(self.reformat_mapper()(fpath), "20260911_report.txt")

    def test_reformat_keeps_name_without_prefix(self):
        fpath = self.create("report.txt")
        self.assertEqual(self.reformat_mapper()(fpath), "report.txt")

    def test_reformat_to_other_format(self):
        fpath = self.create("20260911_report.txt")
        mapper = self.reformat_mapper(date_format="%Y-%m-%d")
        self.assertEqual(mapper(fpath), "2026-09-11_report.txt")

    def test_remove_keeps_name_without_prefix(self):
        fpath = self.create("report.txt")
        self.assertEqual(self.remove_mapper()(fpath), "report.txt")


if __name__ == "__main__":
    unittest.main()
