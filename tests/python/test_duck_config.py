#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""duck-config 命令的端到端测试 (子进程执行, 不污染仓库目录)

运行: python tests/python/test_duck_config.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
SCRIPT_PATH = os.path.join(PROJECT_ROOT, "duck_rush", "config", "duck-config.py")


def run_duck_config(args, cwd):
    """在指定 cwd 下执行 duck-config, 返回 (返回码, stdout, stderr)"""
    env = dict(os.environ)
    # 用仓库内的 duck_utils, 避免命中 site-packages 里的旧拷贝
    env["PYTHONPATH"] = PROJECT_ROOT
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, SCRIPT_PATH] + list(args),
        cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return (proc.returncode,
            proc.stdout.decode("utf-8", errors="replace"),
            proc.stderr.decode("utf-8", errors="replace"))


class DuckConfigTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self._tmp.name
        self.global_dir = os.path.join(self.cwd, "fake-home")
        os.makedirs(self.global_dir)
        # 把 HOME 指到临时目录, 使全局配置也落在临时目录里
        self._old_home = os.environ.get("HOME")
        self._old_userprofile = os.environ.get("USERPROFILE")
        os.environ["HOME"] = self.global_dir
        os.environ["USERPROFILE"] = self.global_dir

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        if self._old_userprofile is None:
            os.environ.pop("USERPROFILE", None)
        else:
            os.environ["USERPROFILE"] = self._old_userprofile
        self._tmp.cleanup()

    @property
    def project_config(self):
        return os.path.join(self.cwd, ".duck-rush.json")

    def read_project(self):
        with open(self.project_config, "r", encoding="utf-8") as fp:
            return json.load(fp)

    def read_global(self):
        path = os.path.join(self.global_dir, ".duck-rush", "config.json")
        with open(path, "r", encoding="utf-8") as fp:
            return json.load(fp)

    def test_help_has_no_side_effect(self):
        code, out, _ = run_duck_config(["-h"], self.cwd)
        self.assertEqual(code, 0)
        self.assertTrue(out.strip())
        self.assertFalse(os.path.exists(self.project_config),
                         "-h 不应创建配置文件")

    def test_no_command_prints_help(self):
        code, out, _ = run_duck_config([], self.cwd)
        self.assertEqual(code, 0)
        self.assertIn("usage", out.lower())

    def test_set_and_get(self):
        self.assertEqual(run_duck_config(["set", "name", "duck"], self.cwd)[0], 0)
        code, out, _ = run_duck_config(["get", "name"], self.cwd)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "duck")

    def test_value_type_auto(self):
        run_duck_config(["set", "port", "8080"], self.cwd)
        run_duck_config(["set", "debug", "true"], self.cwd)
        data = self.read_project()
        self.assertEqual(data["port"], 8080)
        self.assertEqual(data["debug"], True)

    def test_value_type_str(self):
        run_duck_config(["set", "ver", "1.0", "--type", "str"], self.cwd)
        self.assertEqual(self.read_project()["ver"], "1.0")

    def test_get_json_output(self):
        run_duck_config(["set", "tags", '["a","b"]'], self.cwd)
        code, out, _ = run_duck_config(["get", "tags", "--json"], self.cwd)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), ["a", "b"])

    def test_get_missing_key(self):
        code, _, err = run_duck_config(["get", "nope"], self.cwd)
        self.assertEqual(code, 1)
        self.assertIn("nope", err)

    def test_global_flag(self):
        run_duck_config(["set", "editor", "code", "--global"], self.cwd)
        self.assertFalse(os.path.exists(self.project_config))
        self.assertEqual(self.read_global()["editor"], "code")

    def test_project_wins_over_global(self):
        run_duck_config(["set", "a", "global-value", "--global"], self.cwd)
        run_duck_config(["set", "a", "project-value"], self.cwd)
        code, out, _ = run_duck_config(["get", "a"], self.cwd)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "project-value")

    def test_list_with_source(self):
        run_duck_config(["set", "a", "1", "--global"], self.cwd)
        run_duck_config(["set", "b", "2"], self.cwd)
        code, out, _ = run_duck_config(["list", "--source"], self.cwd)
        self.assertEqual(code, 0)
        self.assertIn("[global]", out)
        self.assertIn("[project]", out)

    def test_list_empty(self):
        code, out, _ = run_duck_config(["list"], self.cwd)
        self.assertEqual(code, 0)
        self.assertIn("无配置", out)

    def test_where(self):
        code, out, _ = run_duck_config(["where"], self.cwd)
        self.assertEqual(code, 0)
        self.assertIn(".duck-rush.json", out)
        self.assertIn("config.json", out)

    def test_unset(self):
        run_duck_config(["set", "a", "1"], self.cwd)
        self.assertEqual(run_duck_config(["unset", "a"], self.cwd)[0], 0)
        self.assertNotIn("a", self.read_project())

    def test_unset_missing_key(self):
        code, _, err = run_duck_config(["unset", "nope"], self.cwd)
        self.assertEqual(code, 1)
        self.assertIn("nope", err)

    def test_unset_hints_remaining_global(self):
        run_duck_config(["set", "a", "global-value", "--global"], self.cwd)
        run_duck_config(["set", "a", "project-value"], self.cwd)
        code, out, _ = run_duck_config(["unset", "a"], self.cwd)
        self.assertEqual(code, 0)
        self.assertIn("global", out)

    def test_export_and_import(self):
        run_duck_config(["set", "a", "1"], self.cwd)
        backup = os.path.join(self.cwd, "backup.json")
        self.assertEqual(run_duck_config(["export", backup], self.cwd)[0], 0)
        with open(backup, "r", encoding="utf-8") as fp:
            self.assertEqual(json.load(fp), {"a": 1})

        run_duck_config(["unset", "a"], self.cwd)
        code, out, _ = run_duck_config(["import", backup], self.cwd)
        self.assertEqual(code, 0)
        self.assertIn("已导入", out)
        self.assertEqual(self.read_project(), {"a": 1})

    def test_import_from_stdin(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = PROJECT_ROOT
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, SCRIPT_PATH, "import", "-"],
            cwd=self.cwd, env=env, input=b'{"b": 2}',
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8"))
        self.assertEqual(self.read_project(), {"b": 2})

    def test_import_invalid_json(self):
        bad = os.path.join(self.cwd, "bad.json")
        with open(bad, "w", encoding="utf-8") as fp:
            fp.write("[1, 2]")
        code, _, err = run_duck_config(["import", bad], self.cwd)
        self.assertEqual(code, 1)
        self.assertIn("导入失败", err)


class TestEditorCmd(unittest.TestCase):
    """编辑器的选择逻辑 (只构造命令, 不真的启动编辑器)"""

    def load_module(self):
        import importlib.util
        # 优先使用仓库内的 duck_utils, 避免命中 site-packages 里的旧拷贝
        if PROJECT_ROOT not in sys.path:
            sys.path.insert(0, PROJECT_ROOT)
        spec = importlib.util.spec_from_file_location("duck_config", SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_env_editor_wins(self):
        os.environ.pop("VISUAL", None)
        os.environ["EDITOR"] = "myeditor -w"
        try:
            cmd = self.load_module().build_editor_cmd("/tmp/a.json")
        finally:
            os.environ.pop("EDITOR", None)
        self.assertEqual(cmd, ["myeditor", "-w", "/tmp/a.json"])

    def test_platform_default_ends_with_path(self):
        os.environ.pop("VISUAL", None)
        os.environ.pop("EDITOR", None)
        self.assertEqual(self.load_module().build_editor_cmd("/tmp/a.json")[-1],
                         "/tmp/a.json")


if __name__ == "__main__":
    unittest.main()
