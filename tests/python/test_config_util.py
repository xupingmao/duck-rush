#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""duck_utils.config_util 的单元测试 (仅依赖标准库)

运行: python tests/python/test_config_util.py
"""
import json
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
# 优先使用仓库内的 duck_utils, 避免命中 site-packages 里的旧拷贝
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from duck_utils import config_util  # noqa: E402


class ConfigUtilTest(unittest.TestCase):
    """需要隔离项目级/全局级配置路径的用例基类"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self.tmpdir = self._tmp.name
        self.global_path = os.path.join(self.tmpdir, "global-config.json")

        self._orig_getcwd = os.getcwd
        self._orig_global_path = config_util.get_global_path
        os.getcwd = lambda: self.cwd
        config_util.get_global_path = lambda: self.global_path

    def tearDown(self):
        os.getcwd = self._orig_getcwd
        config_util.get_global_path = self._orig_global_path
        self._tmp.cleanup()

    def write_global(self, data):
        with open(self.global_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp)

    def read_project(self):
        path = config_util.get_project_path(self.cwd)
        with open(path, "r", encoding="utf-8") as fp:
            return json.load(fp)

    def write_project(self, data):
        with open(config_util.get_project_path(self.cwd), "w", encoding="utf-8") as fp:
            json.dump(data, fp)


class TestParseValue(ConfigUtilTest):

    def test_number(self):
        self.assertEqual(config_util.parse_value("123"), 123)

    def test_bool(self):
        self.assertEqual(config_util.parse_value("true"), True)

    def test_list(self):
        self.assertEqual(config_util.parse_value('["a", "b"]'), ["a", "b"])

    def test_null(self):
        self.assertIsNone(config_util.parse_value("null"))

    def test_plain_text(self):
        self.assertEqual(config_util.parse_value("abc"), "abc")

    def test_leading_zero_keeps_string(self):
        # 前导零不是合法 JSON 数字, 应保持字符串
        self.assertEqual(config_util.parse_value("0755"), "0755")


class TestConvertValue(ConfigUtilTest):

    def test_auto(self):
        self.assertEqual(config_util.convert_value("1.5"), 1.5)

    def test_str(self):
        self.assertEqual(config_util.convert_value("123", "str"), "123")

    def test_int(self):
        self.assertEqual(config_util.convert_value("42", "int"), 42)

    def test_float(self):
        self.assertEqual(config_util.convert_value("1.5", "float"), 1.5)

    def test_bool(self):
        self.assertTrue(config_util.convert_value("yes", "bool"))
        self.assertFalse(config_util.convert_value("off", "bool"))

    def test_json(self):
        self.assertEqual(config_util.convert_value('{"a": 1}', "json"), {"a": 1})

    def test_int_error(self):
        with self.assertRaises(ValueError):
            config_util.convert_value("abc", "int")

    def test_unknown_type(self):
        with self.assertRaises(ValueError):
            config_util.convert_value("abc", "unknown")


class TestFormatValue(ConfigUtilTest):

    def test_str_as_is(self):
        self.assertEqual(config_util.format_value("hello"), "hello")

    def test_non_str_as_json(self):
        self.assertEqual(config_util.format_value([1, 2]), "[1, 2]")
        self.assertEqual(config_util.format_value(None), "null")


class TestConfigFile(ConfigUtilTest):

    def test_missing_file_returns_empty(self):
        self.assertEqual(
            config_util.ConfigFile(os.path.join(self.tmpdir, "nope.json")).load(), {})

    def test_broken_json_returns_empty(self):
        path = os.path.join(self.tmpdir, "broken.json")
        with open(path, "w", encoding="utf-8") as fp:
            fp.write("{not json")
        self.assertEqual(config_util.ConfigFile(path).load(), {})

    def test_non_dict_returns_empty(self):
        path = os.path.join(self.tmpdir, "list.json")
        with open(path, "w", encoding="utf-8") as fp:
            fp.write("[1, 2]")
        self.assertEqual(config_util.ConfigFile(path).load(), {})

    def test_save_and_load_roundtrip(self):
        path = os.path.join(self.tmpdir, "a.json")
        config_util.ConfigFile(path).save({"b": 2, "a": 1})
        self.assertEqual(config_util.ConfigFile(path).load(), {"a": 1, "b": 2})

    def test_save_creates_parent_dir(self):
        path = os.path.join(self.tmpdir, "sub", "dir", "a.json")
        config_util.ConfigFile(path).save({"a": 1})
        self.assertTrue(os.path.isfile(path))

    def test_save_leaves_no_tmp_file(self):
        path = os.path.join(self.tmpdir, "a.json")
        config_util.ConfigFile(path).save({"a": 1})
        left = [name for name in os.listdir(self.tmpdir) if name.endswith(".tmp")]
        self.assertEqual(left, [])


class TestScopes(ConfigUtilTest):

    def test_project_path(self):
        self.assertEqual(
            config_util.get_project_path(self.cwd),
            os.path.join(self.cwd, ".duck-rush.json"))

    def test_global_path_can_be_patched(self):
        self.assertEqual(config_util.get_global_path(), self.global_path)

    def test_merged_project_wins(self):
        self.write_global({"a": "global-a", "b": "global-b"})
        self.write_project({"a": "project-a"})
        merged = config_util.load_merged(self.cwd)
        self.assertEqual(merged["a"], "project-a")
        self.assertEqual(merged["b"], "global-b")

    def test_merged_with_source(self):
        self.write_global({"a": 1})
        self.write_project({"b": 2})
        result = config_util.load_merged_with_source(self.cwd)
        self.assertEqual(result["a"]["scope"], config_util.SCOPE_GLOBAL)
        self.assertEqual(result["b"]["scope"], config_util.SCOPE_PROJECT)

    def test_get_value_default(self):
        self.assertIsNone(config_util.get_value("missing", cwd=self.cwd))
        self.assertEqual(config_util.get_value("missing", "x", cwd=self.cwd), "x")

    def test_get_value_from_global(self):
        self.write_global({"a": 1})
        self.assertEqual(config_util.get_value("a", cwd=self.cwd), 1)


class TestWrite(ConfigUtilTest):

    def test_set_writes_project_by_default(self):
        config_util.set_value("a", 1, cwd=self.cwd)
        self.assertEqual(self.read_project(), {"a": 1})
        self.assertFalse(os.path.exists(self.global_path))

    def test_set_global(self):
        config_util.set_value("a", 1, config_util.SCOPE_GLOBAL, cwd=self.cwd)
        with open(self.global_path, "r", encoding="utf-8") as fp:
            self.assertEqual(json.load(fp), {"a": 1})

    def test_unset_returns_false_when_missing(self):
        self.assertFalse(config_util.unset_value("a", cwd=self.cwd))

    def test_unset_only_removes_one_layer(self):
        self.write_global({"a": "global"})
        config_util.set_value("a", "project", cwd=self.cwd)
        self.assertTrue(config_util.unset_value("a", cwd=self.cwd))
        self.assertEqual(config_util.load_scope(config_util.SCOPE_GLOBAL), {"a": "global"})
        # 项目级删掉后, 生效值回落到全局级
        self.assertEqual(config_util.get_value("a", cwd=self.cwd), "global")

    def test_import_overwrite(self):
        self.write_project({"a": 1, "b": 2})
        count = config_util.import_values(
            {"b": 20, "c": 3}, config_util.SCOPE_PROJECT, cwd=self.cwd)
        self.assertEqual(count, 2)
        self.assertEqual(self.read_project(), {"a": 1, "b": 20, "c": 3})

    def test_import_keep_existing(self):
        self.write_project({"a": 1})
        count = config_util.import_values(
            {"a": 100, "b": 2}, config_util.SCOPE_PROJECT,
            cwd=self.cwd, overwrite=False)
        self.assertEqual(count, 1)
        self.assertEqual(self.read_project(), {"a": 1, "b": 2})

    def test_import_empty_returns_zero(self):
        self.assertEqual(
            config_util.import_values({}, config_util.SCOPE_PROJECT, cwd=self.cwd), 0)

    def test_null_is_a_value(self):
        config_util.set_value("a", None, cwd=self.cwd)
        self.assertIn("a", self.read_project())
        self.assertIsNone(config_util.get_value("a", "fallback", cwd=self.cwd))


if __name__ == "__main__":
    unittest.main()
