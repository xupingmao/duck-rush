"""duck-prevent-sleep 的单元测试（仅依赖标准库）

运行: python duck_rush/os/test_duck_prevent_sleep.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _load():
    """按文件名加载脚本（文件名带连字符，无法直接 import）"""
    import importlib.util

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "duck-prevent-sleep.py")
    spec = importlib.util.spec_from_file_location("duck_prevent_sleep", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dps = _load()


class TestWindowsFlags(unittest.TestCase):

    def test_default_allows_screen_off(self):
        flags = dps.windows_execution_flags(False)
        self.assertEqual(flags, dps.ES_CONTINUOUS | dps.ES_SYSTEM_REQUIRED)
        self.assertEqual(flags & dps.ES_DISPLAY_REQUIRED, 0)

    def test_keep_screen_adds_display_required(self):
        flags = dps.windows_execution_flags(True)
        self.assertEqual(
            flags,
            dps.ES_CONTINUOUS | dps.ES_SYSTEM_REQUIRED | dps.ES_DISPLAY_REQUIRED,
        )


class TestMacArgs(unittest.TestCase):

    def test_default_allows_screen_off(self):
        self.assertEqual(dps.mac_caffeinate_args(False), ["caffeinate", "-i", "-m"])

    def test_keep_screen_adds_display_flags(self):
        self.assertEqual(
            dps.mac_caffeinate_args(True),
            ["caffeinate", "-d", "-i", "-m", "-u"],
        )


class TestFormatRemaining(unittest.TestCase):

    def test_within_one_day(self):
        self.assertEqual(dps.format_remaining(3661), "01:01:01")

    def test_over_one_day(self):
        self.assertEqual(dps.format_remaining(86400 * 2 + 62), "2 天 00:01:02")

    def test_negative_truncated(self):
        self.assertEqual(dps.format_remaining(-5), "00:00:00")

    def test_duration_minutes(self):
        self.assertEqual(dps.format_duration_minutes(144000), "100 天 00:00:00")


if __name__ == "__main__":
    unittest.main()
