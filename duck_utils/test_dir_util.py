# -*- coding: utf-8 -*-
"""duck_utils/dir_util.py 单元测试(目录筛选与遍历)。

直接运行:  python duck_utils/test_dir_util.py
"""

import argparse
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from duck_utils.dir_util import (DEFAULT_IGNORE_DIRS, DirFilter,
                                 add_dir_filter_args, dir_filter_from_args,
                                 match_dir_patterns, split_patterns, walk_dir)

# 测试用的目录结构(相对根的路径)
TREE = (
    "main.py",
    "src/a.py",
    "src/lib/b.py",
    "src/vendor/v.py",
    "test/test_a.py",
    "node_modules/pkg/x.py",
    "dist/d.py",
    "docs/readme.txt",
)


def build_tree(root: str) -> None:
    """在 root 下创建测试目录结构"""
    for rel in TREE:
        fpath = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as fp:
            fp.write("# %s\n" % rel)


class BaseTreeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dir_util_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        build_tree(self.tmp)

    def rel_set(self, paths):
        """把绝对路径集合转成 '/' 分隔的相对路径集合, 便于断言"""
        return {os.path.relpath(p, self.tmp).replace("\\", "/") for p in paths}


class TestSplitPatterns(unittest.TestCase):
    def test_comma_and_repeat(self):
        self.assertEqual(split_patterns(["src,lib", "test"]), ["src", "lib", "test"])

    def test_strip_whitespace_and_slashes(self):
        self.assertEqual(split_patterns([" src , lib/ ", "  "]), ["src", "lib"])

    def test_none_and_empty(self):
        self.assertEqual(split_patterns(None), [])
        self.assertEqual(split_patterns([]), [])

    def test_windows_separator(self):
        self.assertEqual(split_patterns([r"src\lib"]), ["src/lib"])


class TestMatchDirPatterns(unittest.TestCase):
    def test_match_by_name(self):
        self.assertTrue(match_dir_patterns("a/b/src", "src", ["src"]))

    def test_match_by_relpath(self):
        self.assertTrue(match_dir_patterns("src/vendor", "vendor", ["src/vendor"]))

    def test_match_by_prefix(self):
        # 命中父目录后, 其子目录也应命中
        self.assertTrue(match_dir_patterns("src/lib/deep", "deep", ["src/lib"]))

    def test_match_by_glob(self):
        self.assertTrue(match_dir_patterns("a/test", "test", ["*/test"]))
        self.assertTrue(match_dir_patterns("src/vendor", "vendor", ["src/*"]))

    def test_no_match(self):
        self.assertFalse(match_dir_patterns("src", "src", ["lib"]))
        self.assertFalse(match_dir_patterns("src", "src", []))


class TestDirFilter(unittest.TestCase):
    def test_default_ignore_dirs(self):
        df = DirFilter()
        self.assertTrue(df.should_skip("node_modules", "node_modules"))
        self.assertFalse(df.should_skip("src", "src"))
        self.assertIn(".git", DEFAULT_IGNORE_DIRS)

    def test_custom_ignore_dirs(self):
        df = DirFilter(ignore_dirs=["only_this"])
        self.assertTrue(df.should_skip("only_this", "only_this"))
        self.assertFalse(df.should_skip("node_modules", "node_modules"))

    def test_exclude(self):
        df = DirFilter(exclude_dirs=["test", "src/vendor"])
        self.assertTrue(df.should_skip("test", "test"))
        self.assertTrue(df.should_skip("src/vendor", "vendor"))
        self.assertFalse(df.should_skip("src", "src"))

    def test_include_empty_means_all(self):
        df = DirFilter()
        self.assertTrue(df.is_included("src", "src", False))

    def test_include_only_matched(self):
        df = DirFilter(include_dirs=["src"])
        self.assertTrue(df.is_included("src", "src", False))
        self.assertFalse(df.is_included("test", "test", False))

    def test_include_inherits_from_parent(self):
        df = DirFilter(include_dirs=["src"])
        self.assertTrue(df.is_included("src/lib", "lib", True))


class TestWalkDir(BaseTreeTest):
    def accept_py(self, path):
        return os.path.splitext(path)[1].lower() == ".py"

    def test_walk_all_skips_ignore_dirs(self):
        found = self.rel_set(walk_dir(self.tmp, self.accept_py))
        self.assertEqual(found, {
            "main.py", "src/a.py", "src/lib/b.py", "src/vendor/v.py",
            "test/test_a.py",
        })
        self.assertNotIn("node_modules/pkg/x.py", found)
        self.assertNotIn("dist/d.py", found)

    def test_walk_with_include_dirs(self):
        df = DirFilter(include_dirs=["src"])
        found = self.rel_set(walk_dir(self.tmp, self.accept_py, df))
        self.assertEqual(found, {"src/a.py", "src/lib/b.py", "src/vendor/v.py"})

    def test_walk_with_multiple_include_dirs(self):
        df = DirFilter(include_dirs=["src", "test"])
        found = self.rel_set(walk_dir(self.tmp, self.accept_py, df))
        self.assertEqual(found, {
            "src/a.py", "src/lib/b.py", "src/vendor/v.py", "test/test_a.py",
        })

    def test_walk_with_exclude_dirs(self):
        df = DirFilter(exclude_dirs=["src/vendor"])
        found = self.rel_set(walk_dir(self.tmp, self.accept_py, df))
        self.assertNotIn("src/vendor/v.py", found)
        self.assertIn("src/a.py", found)

    def test_include_and_exclude_combined(self):
        df = DirFilter(include_dirs=["src"], exclude_dirs=["src/vendor"])
        found = self.rel_set(walk_dir(self.tmp, self.accept_py, df))
        self.assertEqual(found, {"src/a.py", "src/lib/b.py"})

    def test_root_name_matched_by_include(self):
        # 根目录自身命中 include 时, 其下文件全部收录
        src_root = os.path.join(self.tmp, "src")
        df = DirFilter(include_dirs=["src"])
        relative = lambda p: os.path.relpath(p, src_root).replace("\\", "/")  # noqa: E731
        found = {relative(p) for p in walk_dir(src_root, self.accept_py, df)}
        self.assertEqual(found, {"a.py", "lib/b.py", "vendor/v.py"})

    def test_accept_filters_extension(self):
        def accept_txt(path):
            return os.path.splitext(path)[1].lower() == ".txt"
        found = self.rel_set(walk_dir(self.tmp, accept_txt))
        self.assertEqual(found, {"docs/readme.txt"})

    def test_symlink_dir_not_followed(self):
        """符号链接目录不被跟随, 避免软链成环"""
        loop = os.path.join(self.tmp, "loop")
        try:
            os.symlink(self.tmp, loop)
        except (OSError, NotImplementedError):
            self.skipTest("当前环境不支持创建符号链接")
        found = self.rel_set(walk_dir(self.tmp, self.accept_py))
        self.assertTrue(all(not p.startswith("loop") for p in found))


class TestArgparseHelper(unittest.TestCase):
    def test_add_and_parse(self):
        parser = argparse.ArgumentParser()
        add_dir_filter_args(parser)
        args = parser.parse_args(["-d", "src,lib", "-x", "test", "-d", "app"])
        df = dir_filter_from_args(args)
        self.assertEqual(df.include_dirs, ["src", "lib", "app"])
        self.assertEqual(df.exclude_dirs, ["test"])

    def test_default_no_filter(self):
        parser = argparse.ArgumentParser()
        add_dir_filter_args(parser)
        df = dir_filter_from_args(parser.parse_args([]))
        self.assertEqual(df.include_dirs, [])
        self.assertEqual(df.exclude_dirs, [])


if __name__ == "__main__":
    unittest.main()
