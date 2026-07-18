# -*- coding: utf-8 -*-
"""duck-json 单元测试。

直接运行:  python duck_rush/text/test_duck_json.py

内部算子/函数通过 importlib 直接加载模块测试;
CLI 行为通过子进程运行 duck-json.py 做端到端验证。
"""

import importlib.util
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "duck-json.py")


def load_mod():
    """以 importlib 加载带连字符的脚本模块。"""
    spec = importlib.util.spec_from_file_location("duck_json_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(args, stdin_text=""):
    """运行 CLI 并返回 stdout 字符串。"""
    proc = subprocess.run(
        [sys.executable, SCRIPT] + args,
        input=stdin_text, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError("CLI 失败(%s): %s" % (proc.returncode, proc.stderr))
    return proc.stdout


def rows_jsonl(text):
    """把 JSONL 输出解析为对象列表。"""
    return [json.loads(line) for line in text.splitlines() if line.strip()]


class TestInternal(unittest.TestCase):
    """直接测试算子与辅助函数。"""

    def setUp(self):
        self.m = load_mod()

    def test_scan_op_yields_segments(self):
        scan = self.m.ScanOp('x {"a":1} y [2]')
        kinds = [k for k, _ in scan]
        self.assertEqual(kinds, ["text", "json", "text", "json"])

    def test_filter_op_passes_text(self):
        m = self.m
        scan = m.ScanOp('{"a":1} hello {"a":2}')
        flt = m.FilterOp(scan, m.build_filter('a == 1'))
        out = [(k, v) for k, v in flt]
        # 文本原样透传; json 仅保留匹配项
        self.assertEqual(out[0], ("json", {"a": 1}))
        self.assertEqual(out[1][0], "text")

    def test_filter_op_array_as_whole(self):
        m = self.m
        scan = m.ScanOp('[{"a":1},{"a":9}]')
        flt = m.FilterOp(scan, m.build_filter('a >= 9'))
        out = list(flt)
        # 顶层数组整体过滤后作为一个 json 行
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][1], [{"a": 9}])

    def test_split_op_explodes_array(self):
        m = self.m
        scan = m.ScanOp('[{"a":1},{"a":2}]')
        out = list(m.SplitOp(scan))
        self.assertEqual([v for _, v in out], [{"a": 1}, {"a": 2}])

    def test_group_by_op_single(self):
        m = self.m
        scan = m.ScanOp('[{"g":"x","p":1},{"g":"x","p":3},{"g":"y","p":2}]')
        grp = m.GroupByOp(m.FilterOp(scan, None), ["g"], None, False)
        rows = list(grp)
        self.assertEqual(len(rows), 2)
        by = {r["group"]: r for r in rows}
        self.assertEqual(by["x"]["count"], 2)
        self.assertEqual(by["x"]["stats"]["p"]["avg"], 2.0)
        self.assertEqual(by["x"]["stats"]["p"]["min"], 1)

    def test_group_by_op_multi(self):
        m = self.m
        scan = m.ScanOp('[{"g":"x","r":"a","p":1},{"g":"x","r":"a","p":3},'
                          '{"g":"x","r":"b","p":2}]')
        grp = m.GroupByOp(m.FilterOp(scan, None), ["g", "r"], None, False)
        rows = list(grp)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(isinstance(r["group"], dict) for r in rows))

    def test_group_by_op_count_only(self):
        m = self.m
        scan = m.ScanOp('[{"g":"x"},{"g":"x"},{"g":"y"}]')
        grp = m.GroupByOp(m.FilterOp(scan, None), ["g"], None, True)
        rows = list(grp)
        self.assertEqual({r["group"]: r["count"] for r in rows}, {"x": 2, "y": 1})
        self.assertNotIn("stats", rows[0])

    def test_group_by_op_skips_missing_key(self):
        m = self.m
        scan = m.ScanOp('[{"g":"x"},{"p":1}]')
        grp = m.GroupByOp(m.FilterOp(scan, None), ["g"], None, True)
        rows = list(grp)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["group"], "x")

    def test_sort_op_group_by_count_desc(self):
        m = self.m
        scan = m.ScanOp('[{"g":"x","p":1},{"g":"x","p":2},{"g":"y","p":3}]')
        grp = m.GroupByOp(m.FilterOp(scan, None), ["g"], None, False)
        srt = m.SortOp(grp, m._make_group_key_fn(["count"], ["g"]), True)
        rows = list(srt)
        self.assertEqual([r["group"] for r in rows], ["x", "y"])  # 2,1 倒序

    def test_make_record_key_fn_sorts_numeric(self):
        m = self.m
        fn = m._make_record_key_fn(["age"])
        self.assertEqual(fn(("json", {"age": 3})), (3,))
        self.assertEqual(fn(("json", {"age": "x"})), ("x",))  # 非数值

    def test_discover_numeric_fields(self):
        m = self.m
        recs = [{"a": 1, "b": "x", "c": 2.5}, {"a": 0, "d": True}]
        self.assertEqual(m._discover_numeric_fields(recs), ["a", "c"])
        # 当前实现把 bool 视为非数值(bool 不计入)


class TestCLI(unittest.TestCase):
    """端到端验证命令行行为。"""

    def test_plain_pretty(self):
        out = run([], '{"b":2,"a":1}')
        self.assertIn('  "a": 1', out)

    def test_plain_compact(self):
        out = run(["-c"], '{"b":2,"a":1}')
        self.assertEqual(json.loads(out.strip()), {"b": 2, "a": 1})

    def test_flat_custom_sep(self):
        out = run(["-f", "_"], '{"a":{"b":1}}')
        self.assertIn('"a_b": 1', out)

    def test_filter(self):
        # 顶层数组默认整体过滤, 输出为一个 JSON 数组
        out = run(["--filter", "p > 2", "-c"],
                   '[{"g":"x","p":1},{"g":"y","p":9}]')
        data = json.loads(out.strip())
        self.assertEqual([r["g"] for r in data], ["y"])

    def test_filter_word_op_inside_fieldname(self):
        # 回归: age 中的 "ge" 不应被当成 >= 操作符
        out = run(["--filter", "age >= 2", "--sort-by", "age", "-c"],
                   '[{"name":"b","age":3},{"name":"a","age":9},{"name":"c","age":1}]')
        rows = rows_jsonl(out)
        # 未加 -r, 按 age 升序: 过滤后剩 b(3),a(9) -> b,a
        self.assertEqual([r["name"] for r in rows], ["b", "a"])

    def test_group_jsonl(self):
        out = run(["--group-by", "g", "--stats", "price"],
                   '[{"g":"fruit","price":10},{"g":"fruit","price":20},{"g":"veg","price":5}]')
        rows = rows_jsonl(out)
        self.assertEqual(rows[0]["group"], "fruit")
        self.assertEqual(rows[0]["stats"]["price"]["avg"], 15.0)

    def test_group_table(self):
        out = run(["--group-by", "g", "--stats", "price", "--table"],
                   '[{"g":"fruit","price":10},{"g":"veg","price":5}]')
        self.assertIn("count", out)
        self.assertIn("price.avg", out)

    def test_group_count_only(self):
        out = run(["--group-by", "g", "--count"],
                   '[{"g":"x"},{"g":"x"},{"g":"y"}]')
        rows = rows_jsonl(out)
        self.assertEqual(rows, [{"group": "x", "count": 2},
                               {"group": "y", "count": 1}])

    def test_group_sort_by_price_avg_asc(self):
        out = run(["--group-by", "g", "--stats", "price",
                    "--sort-by", "price.avg"],
                   '[{"g":"fruit","price":10},{"g":"fruit","price":20},{"g":"veg","price":5}]')
        rows = rows_jsonl(out)
        self.assertEqual([r["group"] for r in rows], ["veg", "fruit"])

    def test_group_multi_sort_count_desc(self):
        out = run(["--group-by", "g,r", "--stats", "price", "--table",
                    "--sort-by", "count", "-r"],
                   '[{"g":"f","r":"e","price":10},{"g":"f","r":"e","price":20},'
                   '{"g":"f","r":"w","price":5},{"g":"v","r":"e","price":7}]')
        lines = [l for l in out.splitlines() if l.strip()]
        # 表头 + 3 数据行, 首数据行应为 count=2 的 f e
        self.assertTrue(lines[0].startswith("g"))
        self.assertIn("f", lines[1])

    def test_plain_sort_array_explodes(self):
        out = run(["--sort-by", "age", "-r", "-c"],
                   '[{"name":"b","age":3},{"name":"a","age":9},{"name":"c","age":1}]')
        rows = rows_jsonl(out)
        self.assertEqual([r["name"] for r in rows], ["a", "b", "c"])

    def test_split(self):
        out = run(["-S", "-c"], '[{"a":1},{"a":2}]')
        self.assertEqual(out.strip().splitlines(), ['{"a": 1}', '{"a": 2}'])

    def test_keep_text(self):
        out = run(["-k"], 'before {"a":1} after')
        self.assertIn("before", out)
        self.assertIn("after", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
