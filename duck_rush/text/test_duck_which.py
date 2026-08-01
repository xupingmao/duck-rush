# -*- coding: utf-8 -*-
"""duck-which 单元测试。

直接运行:  python duck_rush/text/test_duck_which.py

内部函数通过 importlib 直接加载模块测试(并打桩 is_windows / _PATHEXT / _path_dirs
以保证跨平台确定性); CLI 行为通过子进程运行 duck-which.py 做端到端验证。
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from typing import List, Optional
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "duck-which.py")


def load_mod():
    """以 importlib 加载带连字符的脚本模块。"""
    spec = importlib.util.spec_from_file_location("duck_which_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(args: List[str], env: Optional[dict] = None) -> "subprocess.CompletedProcess":
    """运行 CLI 并返回 CompletedProcess(不抛出, 由断言判断退出码)。"""
    proc = subprocess.run(
        [sys.executable, SCRIPT] + args,
        env=env, capture_output=True, text=True)
    return proc


def run_with_path(args: List[str], path_dirs: List[str]) -> "subprocess.CompletedProcess":
    """在受控 PATH 下运行 CLI。"""
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(path_dirs)
    return run(args, env=env)


class TestPathextSet(unittest.TestCase):
    """_pathext_set 解析 PATHEXT 环境变量的行为。"""

    def setUp(self):
        self.m = load_mod()

    def test_custom_pathext(self):
        with mock.patch.dict(os.environ, {"PATHEXT": ".EXE;.BAT"}, clear=True):
            self.assertEqual(self.m._pathext_set(), {".exe", ".bat"})

    def test_missing_pathext_uses_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            exts = self.m._pathext_set()
        # 默认集合至少包含常见可执行后缀
        self.assertIn(".exe", exts)
        self.assertIn(".bat", exts)
        self.assertIn(".cmd", exts)


class TestCandidateNames(unittest.TestCase):
    """_candidate_names 根据平台/扩展名生成待试文件名。"""

    def setUp(self):
        self.m = load_mod()
        # 固定一个确定性的后缀集合, 避免受系统 PATHEXT 影响
        self.m._PATHEXT = {".exe", ".bat", ".cmd"}

    def test_windows_no_ext(self):
        with mock.patch.object(self.m, "is_windows", return_value=True):
            cands = self.m._candidate_names("foo")
        self.assertEqual(cands[0], "foo")          # 无后缀本体优先
        self.assertIn("foo.exe", cands)
        self.assertIn("foo.bat", cands)
        self.assertIn("foo.cmd", cands)

    def test_windows_with_ext(self):
        with mock.patch.object(self.m, "is_windows", return_value=True):
            cands = self.m._candidate_names("foo.exe")
        self.assertEqual(cands, ["foo.exe"])       # 已有扩展名只试原名

    def test_unix_no_ext(self):
        with mock.patch.object(self.m, "is_windows", return_value=False):
            cands = self.m._candidate_names("foo")
        self.assertEqual(cands, ["foo"])

    def test_unix_with_ext(self):
        with mock.patch.object(self.m, "is_windows", return_value=False):
            cands = self.m._candidate_names("foo.exe")
        self.assertEqual(cands, ["foo.exe"])


class TestIsExecutable(unittest.TestCase):
    """_is_executable 的跨平台判定。"""

    def setUp(self):
        self.m = load_mod()
        self.m._PATHEXT = {".exe", ".bat", ".cmd"}
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        for root, _dirs, files in os.walk(self.tmp, topdown=False):
            for f in files:
                try:
                    os.remove(os.path.join(root, f))
                except OSError:
                    pass
        try:
            os.rmdir(self.tmp)
        except OSError:
            pass

    def _win(self):
        with mock.patch.object(self.m, "is_windows", return_value=True):
            yield

    def test_windows_ext_ok(self):
        p = os.path.join(self.tmp, "a.exe")
        open(p, "w").close()
        with mock.patch.object(self.m, "is_windows", return_value=True):
            self.assertTrue(self.m._is_executable(p))

    def test_windows_no_ext_ok(self):
        p = os.path.join(self.tmp, "nosuffix")
        open(p, "w").close()
        with mock.patch.object(self.m, "is_windows", return_value=True):
            self.assertTrue(self.m._is_executable(p))

    def test_windows_unknown_ext_rejected(self):
        p = os.path.join(self.tmp, "a.txt")
        open(p, "w").close()
        with mock.patch.object(self.m, "is_windows", return_value=True):
            self.assertFalse(self.m._is_executable(p))

    def test_windows_dir_rejected(self):
        d = os.path.join(self.tmp, "adir")
        os.mkdir(d)
        with mock.patch.object(self.m, "is_windows", return_value=True):
            self.assertFalse(self.m._is_executable(d))

    def test_unix_exec_bit(self):
        p = os.path.join(self.tmp, "bin1")
        open(p, "w").close()
        # NTFS 不实现 Unix 执行位, 故打桩 os.access 以在任意平台验证 Unix 分支逻辑
        with mock.patch.object(self.m, "is_windows", return_value=False), \
                mock.patch.object(self.m.os, "access", return_value=True):
            self.assertTrue(self.m._is_executable(p))
        with mock.patch.object(self.m, "is_windows", return_value=False), \
                mock.patch.object(self.m.os, "access", return_value=False):
            self.assertFalse(self.m._is_executable(p))

    def test_unix_dir_rejected(self):
        d = os.path.join(self.tmp, "adir")
        os.mkdir(d)
        with mock.patch.object(self.m, "is_windows", return_value=False):
            self.assertFalse(self.m._is_executable(d))


class TestFind(unittest.TestCase):
    """_find 在受控 PATH(由 _path_dirs 打桩)下的查找行为。"""

    def setUp(self):
        self.m = load_mod()
        self.dir_a = tempfile.mkdtemp()
        self.dir_b = tempfile.mkdtemp()
        if self.m.is_windows():
            self.name = "tool"
            open(os.path.join(self.dir_a, "tool.bat"), "w").close()
            open(os.path.join(self.dir_b, "tool2.bat"), "w").close()
            # 另放一个无后缀本体, 验证其也能匹配
            open(os.path.join(self.dir_a, "tool"), "w").close()
        else:
            self.name = "tool"
            pa = os.path.join(self.dir_a, "tool")
            open(pa, "w").close()
            os.chmod(pa, 0o755)
            pb = os.path.join(self.dir_b, "tool2")
            open(pb, "w").close()
            os.chmod(pb, 0o755)

    def tearDown(self):
        for d in (self.dir_a, self.dir_b):
            for root, _dirs, files in os.walk(d, topdown=False):
                for f in files:
                    try:
                        os.remove(os.path.join(root, f))
                    except OSError:
                        pass
                try:
                    os.rmdir(root)
                except OSError:
                    pass

    def _find(self, name, all_matches):
        with mock.patch.object(self.m, "_path_dirs",
                               return_value=[self.dir_a, self.dir_b]):
            return self.m._find(name, all_matches)

    def test_first_match(self):
        res = self._find(self.name, False)
        self.assertEqual(len(res), 1)
        self.assertEqual(os.path.dirname(res[0]), self.dir_a)
        self.assertTrue(os.path.basename(res[0]).startswith(self.name))

    def test_all_match(self):
        res = self._find("tool2", True)
        self.assertEqual(len(res), 1)
        self.assertEqual(os.path.dirname(res[0]), self.dir_b)

    def test_with_extension_windows(self):
        if not self.m.is_windows():
            self.skipTest("仅 Windows 路径相关")
        res = self._find("tool.bat", False)
        self.assertEqual(len(res), 1)
        self.assertEqual(os.path.dirname(res[0]), self.dir_a)

    def test_not_found(self):
        res = self._find("no-such-tool-xyz", False)
        self.assertEqual(res, [])


class TestCLI(unittest.TestCase):
    """端到端验证命令行行为。"""

    def setUp(self):
        self.m = load_mod()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        for root, _dirs, files in os.walk(self.tmp, topdown=False):
            for f in files:
                try:
                    os.remove(os.path.join(root, f))
                except OSError:
                    pass
            try:
                os.rmdir(root)
            except OSError:
                pass

    def test_help_exit_zero(self):
        proc = run(["-h"])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("PATH", proc.stdout)

    def test_not_found_exit_one(self):
        proc = run_with_path(["zzz-no-such"], [self.tmp])
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout.strip(), "")

    def test_found_via_path(self):
        if self.m.is_windows():
            fname = "mycmd.bat"
        else:
            fname = "mycmd"
        fpath = os.path.join(self.tmp, fname)
        open(fpath, "w").close()
        if not self.m.is_windows():
            os.chmod(fpath, 0o755)
        proc = run_with_path(["mycmd"], [self.tmp])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), fpath)

    def test_found_then_notfound_exit_zero(self):
        # which 语义: 多个名称中只要有一个找到即退出码 0, 但仍输出已找到的项
        if self.m.is_windows():
            fname = "mycmd.bat"
        else:
            fname = "mycmd"
        fpath = os.path.join(self.tmp, fname)
        open(fpath, "w").close()
        if not self.m.is_windows():
            os.chmod(fpath, 0o755)
        proc = run_with_path(["mycmd", "another-missing"], [self.tmp])
        self.assertEqual(proc.returncode, 0)
        self.assertIn(fpath, proc.stdout)

    def test_all_flag_lists_everything(self):
        if self.m.is_windows():
            f1, f2 = "c.bat", "c.exe"
        else:
            f1, f2 = "c", "c.sh"
        p1 = os.path.join(self.tmp, f1)
        p2 = os.path.join(self.tmp, f2)
        open(p1, "w").close()
        open(p2, "w").close()
        if not self.m.is_windows():
            os.chmod(p1, 0o755)
            os.chmod(p2, 0o755)
        proc = run_with_path(["-a", "c"], [self.tmp])
        self.assertEqual(proc.returncode, 0)
        # 至少应列出一个匹配
        self.assertTrue(proc.stdout.strip())


if __name__ == "__main__":
    unittest.main(verbosity=2)
