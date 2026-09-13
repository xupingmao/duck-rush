# -*- coding: utf-8 -*-
"""duck_utils/find_assign/engine.py 目录筛选相关单元测试。

直接运行:  python duck_utils/find_assign/test_engine.py
"""

import os
import shutil
import sys
import tempfile
import unittest

# 使 `import duck_utils` 指向仓库内的源码(而非已安装的旧版本)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from duck_utils.dir_util import DirFilter
from duck_utils.find_assign.engine import AssignmentFinder

# 测试目录结构: 相对路径 -> 文件内容
FILES = {
    "src/a.py": "user_name = 1\n",
    "src/lib/b.py": "userName = 2\n",
    "test/test_a.py": "user_name = 3\n",
    "docs/readme.txt": "user_name = 4\n",   # 非已知扩展名, 目录遍历时不收录
    "node_modules/pkg/x.py": "user_name = 5\n",
}


class SearchDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="find_assign_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for rel, content in FILES.items():
            fpath = os.path.join(self.tmp, *rel.split("/"))
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, "w", encoding="utf-8") as fp:
                fp.write(content)
        self.finder = AssignmentFinder("user_name")

    def rel_set(self, results):
        return {os.path.relpath(fpath, self.tmp).replace("\\", "/")
                for fpath, _ in results}

    def test_search_dir_basic(self):
        found = self.rel_set(self.finder.search_dir(self.tmp))
        self.assertEqual(found, {"src/a.py", "src/lib/b.py", "test/test_a.py"})

    def test_search_dir_with_include_dirs(self):
        df = DirFilter(include_dirs=["src"])
        found = self.rel_set(self.finder.search_dir(self.tmp, df))
        self.assertEqual(found, {"src/a.py", "src/lib/b.py"})

    def test_search_dir_with_exclude_dirs(self):
        df = DirFilter(exclude_dirs=["src/lib", "test"])
        found = self.rel_set(self.finder.search_dir(self.tmp, df))
        self.assertEqual(found, {"src/a.py"})

    def test_search_dir_include_and_exclude(self):
        df = DirFilter(include_dirs=["src"], exclude_dirs=["src/lib"])
        found = self.rel_set(self.finder.search_dir(self.tmp, df))
        self.assertEqual(found, {"src/a.py"})

    def test_search_targets_dir_filtered_file_kept(self):
        """目录受筛选, 显式传入的文件仍会被搜索"""
        explicit = os.path.join(self.tmp, "test", "test_a.py")
        df = DirFilter(include_dirs=["src"])
        results = self.finder.search_targets([self.tmp, explicit], df)
        found = self.rel_set(results)
        self.assertEqual(found, {"src/a.py", "src/lib/b.py", "test/test_a.py"})


if __name__ == "__main__":
    unittest.main()
