#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""duck_utils.fs_util 日期前缀识别的单元测试 (仅依赖标准库)

运行: python tests/python/test_fs_util_date_prefix.py
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
# 优先使用仓库内的 duck_utils, 避免命中 site-packages 里的旧拷贝
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from duck_utils import fs_util  # noqa: E402


class TestMatchDatePrefix(unittest.TestCase):

    def test_compact(self):
        prefix = fs_util.match_date_prefix("20260911_report.pdf")
        self.assertIsNotNone(prefix)
        assert prefix is not None
        self.assertEqual(prefix.date, "20260911")
        self.assertEqual(prefix.sep, "_")
        self.assertEqual(prefix.text, "20260911_")

    def test_dash(self):
        prefix = fs_util.match_date_prefix("2026-09-11_report.pdf")
        assert prefix is not None
        self.assertEqual(prefix.date, "2026-09-11")

    def test_underscore(self):
        prefix = fs_util.match_date_prefix("2026_09_11_report.pdf")
        assert prefix is not None
        self.assertEqual(prefix.date, "2026_09_11")

    def test_dot(self):
        prefix = fs_util.match_date_prefix("2026.09.11_report.pdf")
        assert prefix is not None
        self.assertEqual(prefix.date, "2026.09.11")

    def test_not_zero_padded(self):
        prefix = fs_util.match_date_prefix("2026-9-1_report.pdf")
        assert prefix is not None
        self.assertEqual(prefix.date, "2026-9-1")

    def test_dash_separator(self):
        prefix = fs_util.match_date_prefix("20260911-report.pdf")
        assert prefix is not None
        self.assertEqual(prefix.sep, "-")

    def test_space_separator(self):
        prefix = fs_util.match_date_prefix("2026-09-11 report.pdf")
        assert prefix is not None
        self.assertEqual(prefix.sep, " ")

    def test_with_time(self):
        prefix = fs_util.match_date_prefix("2026-09-11_123000_report.pdf")
        assert prefix is not None
        self.assertEqual(prefix.text, "2026-09-11_123000_")

    def test_ignores_dirname(self):
        prefix = fs_util.match_date_prefix(os.path.join("a", "b", "20260911_c.txt"))
        assert prefix is not None
        self.assertEqual(prefix.date, "20260911")


class TestNotDatePrefix(unittest.TestCase):
    """不应被识别成日期前缀的情况"""

    def test_plain_name(self):
        self.assertIsNone(fs_util.match_date_prefix("report.pdf"))

    def test_date_is_whole_name(self):
        # 整个文件名就是日期, 不算"前缀"
        self.assertIsNone(fs_util.match_date_prefix("20260911.txt"))

    def test_date_not_at_start(self):
        self.assertIsNone(fs_util.match_date_prefix("IMG_20260911.jpg"))

    def test_invalid_month(self):
        self.assertIsNone(fs_util.match_date_prefix("2026-13-11_report.pdf"))

    def test_invalid_compact_date(self):
        self.assertIsNone(fs_util.match_date_prefix("12345678_report.pdf"))

    def test_short_number(self):
        self.assertIsNone(fs_util.match_date_prefix("2026091_report.pdf"))

    def test_empty(self):
        self.assertIsNone(fs_util.match_date_prefix(""))


class TestHasDatePrefix(unittest.TestCase):

    def test_true(self):
        self.assertTrue(fs_util.has_date_prefix("2026-09-11_a.txt"))

    def test_false(self):
        self.assertFalse(fs_util.has_date_prefix("a.txt"))


class TestStripDatePrefix(unittest.TestCase):

    def test_strip(self):
        self.assertEqual(fs_util.strip_date_prefix("2026-09-11_report.pdf"),
                         "report.pdf")

    def test_keep_name_when_no_prefix(self):
        self.assertEqual(fs_util.strip_date_prefix("report.pdf"), "report.pdf")

    def test_keep_date_only_name(self):
        self.assertEqual(fs_util.strip_date_prefix("20260911.txt"), "20260911.txt")

    def test_keeps_dirname(self):
        name = os.path.join("a", "b", "2026-09-11_report.pdf")
        self.assertEqual(fs_util.strip_date_prefix(name),
                         os.path.join("a", "b", "report.pdf"))


class TestReformatDatePrefix(unittest.TestCase):

    def test_dash_to_compact(self):
        self.assertEqual(
            fs_util.reformat_date_prefix("2026-09-11_report.pdf", "%Y%m%d", "_"),
            "20260911_report.pdf")

    def test_compact_to_dash(self):
        self.assertEqual(
            fs_util.reformat_date_prefix("20260911_report.pdf", "%Y-%m-%d", "_"),
            "2026-09-11_report.pdf")

    def test_underscore_to_compact(self):
        self.assertEqual(
            fs_util.reformat_date_prefix("2026_09_11_report.pdf", "%Y%m%d", "_"),
            "20260911_report.pdf")

    def test_change_separator(self):
        self.assertEqual(
            fs_util.reformat_date_prefix("2026-09-11-report.pdf", "%Y%m%d", "_"),
            "20260911_report.pdf")

    def test_keeps_time_part(self):
        self.assertEqual(
            fs_util.reformat_date_prefix(
                "2026-09-11_123000_report.pdf", "%Y%m%d", "_"),
            "20260911_123000_report.pdf")

    def test_already_target_format(self):
        name = "20260911_report.pdf"
        self.assertEqual(
            fs_util.reformat_date_prefix(name, "%Y%m%d", "_"), name)

    def test_without_prefix(self):
        self.assertEqual(
            fs_util.reformat_date_prefix("report.pdf", "%Y%m%d", "_"),
            "report.pdf")

    def test_keeps_dirname(self):
        name = os.path.join("a", "b", "2026-09-11_report.pdf")
        self.assertEqual(
            fs_util.reformat_date_prefix(name, "%Y%m%d", "_"),
            os.path.join("a", "b", "20260911_report.pdf"))

    def test_custom_format(self):
        self.assertEqual(
            fs_util.reformat_date_prefix("20260911_report.pdf", "%Y/%m", "-"),
            "2026/09-report.pdf")


if __name__ == "__main__":
    unittest.main()
