# -*- coding: utf-8 -*-
"""duck-ls 单元测试。

直接运行:  python duck_rush/fs/test_duck_ls.py

内部函数通过 importlib 直接加载模块测试(文件名带连字符, 不能 import);
CLI 行为通过子进程运行 duck-ls.py 做端到端验证。只依赖标准库。
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "duck-ls.py")


def load_mod():
    """以 importlib 加载带连字符的脚本模块。"""
    spec = importlib.util.spec_from_file_location("duck_ls_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = load_mod()


def run_cli(args):
    """运行 CLI, 返回 (returncode, stdout, stderr)。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, SCRIPT] + args,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    return (proc.returncode,
            proc.stdout.decode("utf-8", errors="replace"),
            proc.stderr.decode("utf-8", errors="replace"))


class TestFormatSize(unittest.TestCase):
    def test_raw_bytes(self):
        self.assertEqual(mod.format_size(1536, False), "1536")

    def test_below_1k_stays_bytes(self):
        self.assertEqual(mod.format_size(1023, True), "1023")

    def test_exact_1k(self):
        self.assertEqual(mod.format_size(1024, True), "1.0K")

    def test_one_decimal_below_10(self):
        self.assertEqual(mod.format_size(1536, True), "1.5K")

    def test_rounded_above_10(self):
        self.assertEqual(mod.format_size(20 * 1024, True), "20K")

    def test_megabyte(self):
        self.assertEqual(mod.format_size(1024 ** 2, True), "1.0M")

    def test_gigabyte(self):
        self.assertEqual(mod.format_size(1024 ** 3, True), "1.0G")


class TestDisplayWidth(unittest.TestCase):
    """中文文件名的对齐依赖显示宽度而不是字符数。"""

    def test_ascii(self):
        self.assertEqual(mod.display_width("abc"), 3)

    def test_cjk_counts_two(self):
        self.assertEqual(mod.display_width("中文"), 4)

    def test_mixed(self):
        self.assertEqual(mod.display_width("a中"), 3)

    def test_empty(self):
        self.assertEqual(mod.display_width(""), 0)

    def test_pad_uses_display_width(self):
        # "中" 显示宽 2, 补到 6 应补 4 个空格(而非按字符数补 5 个)
        self.assertEqual(mod.pad_to_width("中", 6), "中" + " " * 4)

    def test_pad_no_shrink(self):
        self.assertEqual(mod.pad_to_width("abcdef", 3), "abcdef")


class TestExtractColorMode(unittest.TestCase):
    """--color 需要自行摘取, 否则 `--color /tmp` 会被 argparse 吃掉路径。"""

    def test_default_auto(self):
        self.assertEqual(mod.extract_color_mode(["-l"]), (["-l"], "auto"))

    def test_bare_color_is_always(self):
        self.assertEqual(mod.extract_color_mode(["--color"]), ([], "always"))

    def test_color_with_value(self):
        self.assertEqual(mod.extract_color_mode(["--color=never"]), ([], "never"))

    def test_no_color(self):
        self.assertEqual(mod.extract_color_mode(["--no-color"]), ([], "never"))

    def test_path_after_bare_color_is_kept(self):
        # 关键用例: 路径不能被当成 --color 的取值
        self.assertEqual(mod.extract_color_mode(["--color", "/tmp"]),
                         (["/tmp"], "always"))

    def test_double_dash_stops_parsing(self):
        rest, when = mod.extract_color_mode(["--", "--color"])
        self.assertEqual(rest, ["--", "--color"])
        self.assertEqual(when, "auto")

    def test_invalid_value_passed_through(self):
        # 由 main() 负责报错退出, 这里只确认原样带出
        self.assertEqual(mod.extract_color_mode(["--color=bogus"])[1], "bogus")


class DirTestCase(unittest.TestCase):
    """在临时目录里造一批已知条目。"""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="duck-ls-test-")
        self.write("b.txt", "b" * 300)
        self.write("a.txt", "a" * 100)
        self.write(".hidden", "x")
        os.mkdir(os.path.join(self.tmpdir, "sub"))
        # 让 mtime 有确定顺序: a.txt 最新
        now = time.time()
        os.utime(os.path.join(self.tmpdir, "b.txt"), (now - 100, now - 100))
        os.utime(os.path.join(self.tmpdir, "a.txt"), (now, now))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def write(self, name, content):
        with open(os.path.join(self.tmpdir, name), "w", encoding="utf-8") as fp:
            fp.write(content)

    def names(self, entries):
        return [e.name for e in entries]


class TestCollectAndSort(DirTestCase):
    def test_hidden_excluded_by_default(self):
        entries = mod.collect_dir(self.tmpdir, False, False)
        self.assertEqual(self.names(entries), ["a.txt", "b.txt", "sub"])

    def test_almost_all_includes_hidden(self):
        entries = mod.collect_dir(self.tmpdir, False, True)
        self.assertIn(".hidden", self.names(entries))
        self.assertNotIn(".", self.names(entries))

    def test_show_all_includes_dot_entries(self):
        entries = mod.collect_dir(self.tmpdir, True, False)
        names = self.names(entries)
        self.assertIn(".", names)
        self.assertIn("..", names)
        self.assertIn(".hidden", names)

    def test_sort_by_name(self):
        entries = mod.collect_dir(self.tmpdir, False, False)
        ordered = mod.sort_entries(entries, False, False, False)
        self.assertEqual(self.names(ordered), ["a.txt", "b.txt", "sub"])

    def test_sort_reverse(self):
        entries = mod.collect_dir(self.tmpdir, False, False)
        ordered = mod.sort_entries(entries, False, False, True)
        self.assertEqual(self.names(ordered), ["sub", "b.txt", "a.txt"])

    def test_sort_by_time_newest_first(self):
        entries = mod.collect_dir(self.tmpdir, False, False)
        ordered = mod.sort_entries(entries, True, False, False)
        self.assertLess(self.names(ordered).index("a.txt"),
                        self.names(ordered).index("b.txt"))

    def test_sort_by_size_largest_first(self):
        entries = [e for e in mod.collect_dir(self.tmpdir, False, False)
                   if not e.is_dir]
        ordered = mod.sort_entries(entries, False, True, False)
        self.assertEqual(self.names(ordered), ["b.txt", "a.txt"])


class TestRender(DirTestCase):
    def make_opts(self, **kwargs):
        defaults = dict(long_format=False, human=False,
                        one_per_line=False, color=False)
        defaults.update(kwargs)
        return mod.Options(**defaults)

    def test_long_format_has_expected_columns(self):
        entries = mod.collect_dir(self.tmpdir, False, False)
        ordered = mod.sort_entries(entries, False, False, False)
        lines = mod.render_long(ordered, self.make_opts(long_format=True))
        self.assertEqual(len(lines), 3)
        # 权限串 + 链接数 + 属主 + 属组 + 大小 + 时间(3 段) + 名称
        first = lines[0].split()
        # 权限 链接数 属主 属组 大小 月 日 时分/年 名称 = 9 段
        self.assertEqual(len(first), 9)
        self.assertTrue(first[0].startswith("-"))   # 普通文件
        self.assertEqual(first[-1], "a.txt")
        self.assertTrue(lines[-1].startswith("d"))  # sub 是目录

    def test_long_format_human_size(self):
        entries = [e for e in mod.collect_dir(self.tmpdir, False, False)
                   if e.name == "b.txt"]
        lines = mod.render_long(entries,
                                self.make_opts(long_format=True, human=True))
        self.assertIn("300", lines[0])  # 300 字节, 不足 1K 仍显示字节数

    def test_one_per_line(self):
        entries = mod.collect_dir(self.tmpdir, False, False)
        ordered = mod.sort_entries(entries, False, False, False)
        lines = mod.render_columns(ordered, self.make_opts(one_per_line=True), 80)
        self.assertEqual(lines, ["a.txt", "b.txt", "sub"])

    def test_column_major_layout(self):
        # 5 个宽度 1 的名字, 终端宽 8 -> 3 列 2 行, 且先竖向填充
        entries = [mod.Entry(name=n, path=n, st=os.stat(self.tmpdir),
                             is_dir=False, is_link=False, link_target="")
                   for n in ["a", "b", "c", "d", "e"]]
        lines = mod.render_columns(entries, self.make_opts(), 8)
        self.assertEqual(lines, ["a  c  e", "b  d"])

    def test_narrow_terminal_falls_back_to_one_column(self):
        entries = mod.collect_dir(self.tmpdir, False, False)
        ordered = mod.sort_entries(entries, False, False, False)
        lines = mod.render_columns(ordered, self.make_opts(), 3)
        self.assertEqual(lines, ["a.txt", "b.txt", "sub"])

    def test_empty_dir_renders_nothing(self):
        empty = tempfile.mkdtemp(prefix="duck-ls-empty-")
        try:
            entries = mod.collect_dir(empty, False, False)
            self.assertEqual(mod.render_columns(entries, self.make_opts(), 80), [])
            self.assertEqual(mod.render_long(entries, self.make_opts()), [])
        finally:
            shutil.rmtree(empty, ignore_errors=True)

    def test_color_wraps_dir_name(self):
        entries = [e for e in mod.collect_dir(self.tmpdir, False, False)
                   if e.name == "sub"]
        lines = mod.render_columns(entries, self.make_opts(color=True), 80)
        self.assertIn(mod.COLOR_DIR, lines[0])
        self.assertIn(mod.COLOR_RESET, lines[0])


class TestCli(DirTestCase):
    """端到端行为, 特别是 -h 的双重语义。"""

    def test_bare_h_prints_help_without_listing(self):
        # install.py 会执行 `duck-ls -h` 取首行作为命令简介, 必须无副作用
        code, out, _ = run_cli(["-h"])
        self.assertEqual(code, 0)
        self.assertIn("duck-ls", out.splitlines()[0])
        self.assertIn("--color", out)
        # 不应该列出当前目录的内容
        self.assertNotIn("test_duck_ls.py", out)

    def test_long_help(self):
        code, out, _ = run_cli(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("duck-ls", out)

    def test_combined_lh_lists_and_not_help(self):
        # 别名 ll="duck-ls -lh --color" 依赖这个行为
        code, out, _ = run_cli(["-lh", self.tmpdir])
        self.assertEqual(code, 0)
        self.assertIn("a.txt", out)
        self.assertNotIn("用法", out)

    def test_h_after_other_flag_is_human_readable(self):
        code, out, _ = run_cli(["-l", "-h", self.tmpdir])
        self.assertEqual(code, 0)
        self.assertIn("a.txt", out)

    def test_piped_output_is_one_per_line(self):
        code, out, _ = run_cli([self.tmpdir])
        self.assertEqual(code, 0)
        self.assertEqual([l for l in out.splitlines() if l],
                         ["a.txt", "b.txt", "sub"])

    def test_piped_output_has_no_cr(self):
        # 便于 duck-ls | xargs / grep 在 Windows 下正常工作
        _, out, _ = run_cli([self.tmpdir])
        self.assertNotIn("\r", out)

    def test_all_flag(self):
        _, out, _ = run_cli(["-A", self.tmpdir])
        self.assertIn(".hidden", out)

    def test_color_never_has_no_escape(self):
        _, out, _ = run_cli(["--color=never", self.tmpdir])
        self.assertNotIn("\033[", out)

    def test_color_always_has_escape(self):
        _, out, _ = run_cli(["--color", self.tmpdir])
        self.assertIn("\033[", out)

    def test_bare_color_keeps_path_operand(self):
        # `--color <路径>` 里的路径不能被当成 --color 的取值
        code, out, _ = run_cli(["--color", self.tmpdir])
        self.assertEqual(code, 0)
        self.assertIn("a.txt", out)

    def test_missing_path_exits_2(self):
        code, _, err = run_cli([os.path.join(self.tmpdir, "nope")])
        self.assertEqual(code, 2)
        self.assertIn("nope", err)

    def test_invalid_color_exits_2(self):
        code, _, err = run_cli(["--color=bogus"])
        self.assertEqual(code, 2)
        self.assertIn("--color", err)

    def test_dir_itself(self):
        _, out, _ = run_cli(["-d", self.tmpdir])
        self.assertEqual(out.strip(), self.tmpdir)

    def test_multiple_operands_print_headers(self):
        other = tempfile.mkdtemp(prefix="duck-ls-other-")
        try:
            _, out, _ = run_cli([self.tmpdir, other])
            self.assertIn("%s:" % self.tmpdir, out)
            self.assertIn("%s:" % other, out)
        finally:
            shutil.rmtree(other, ignore_errors=True)

    def test_file_operand_shown_as_given(self):
        target = os.path.join(self.tmpdir, "a.txt")
        _, out, _ = run_cli([target])
        self.assertEqual(out.strip(), target)


if __name__ == "__main__":
    unittest.main(verbosity=2)
