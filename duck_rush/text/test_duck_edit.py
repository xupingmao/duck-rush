# -*- coding: utf-8 -*-
"""duck-edit（Textual 双栏编辑器）单元测试。

直接运行:  python duck_rush/text/test_duck_edit.py

内部函数（编解码 / 纯逻辑 / 高亮）通过 importlib 直接加载模块测试;
App 的端到端行为通过 Textual 的 run_test() 在无头模式下驱动验证。
"""

import importlib.util
import os
import tempfile
import unittest
from unittest import IsolatedAsyncioTestCase

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "duck-edit.py")


def load_mod():
    """以 importlib 加载带连字符的脚本模块。"""
    spec = importlib.util.spec_from_file_location("duck_edit_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestCodec(unittest.TestCase):
    """编码 / 换行符的读写应原样保留。"""

    def setUp(self):
        self.m = load_mod()
        self.tmp = tempfile.mkdtemp(prefix="duck_edit_")

    def _path(self, name):
        return os.path.join(self.tmp, name)

    def _roundtrip(self, src_bytes, encoding):
        path = self._path("rt.bin")
        with open(path, "wb") as fp:
            fp.write(src_bytes)
        text, enc, newline = self.m._read_file(path)
        self.assertEqual(enc, encoding)
        # 换行已统一为 \n
        self.assertNotIn("\r", text)
        out = self._path("out.bin")
        self.m._write_file(out, text, enc, newline)
        with open(out, "rb") as fp:
            self.assertEqual(fp.read(), src_bytes)

    def test_utf8_roundtrip(self):
        self._roundtrip("中文 abc 123\n".encode("utf-8"), "utf-8")

    def test_utf8sig_roundtrip(self):
        self._roundtrip("x = 1\n".encode("utf-8-sig"), "utf-8-sig")

    def test_utf16_roundtrip(self):
        self._roundtrip("中文\n".encode("utf-16"), "utf-16")

    def test_gbk_roundtrip(self):
        self._roundtrip("中文内容\n".encode("gbk"), "gbk")

    def test_crlf_preserved(self):
        m = self.m
        src = b"a\r\nb\r\n"
        path = self._path("crlf.txt")
        with open(path, "wb") as fp:
            fp.write(src)
        text, enc, newline = m._read_file(path)
        self.assertEqual(newline, "\r\n")
        self.assertEqual(text, "a\nb\n")
        out = self._path("out.txt")
        m._write_file(out, text, enc, newline)
        with open(out, "rb") as fp:
            self.assertEqual(fp.read(), src)

    def test_lf_preserved(self):
        m = self.m
        src = b"a\nb\n"
        path = self._path("lf.txt")
        with open(path, "wb") as fp:
            fp.write(src)
        text, enc, newline = m._read_file(path)
        self.assertEqual(newline, "\n")
        out = self._path("out.txt")
        m._write_file(out, text, enc, newline)
        with open(out, "rb") as fp:
            self.assertEqual(fp.read(), src)

    def test_missing_file_is_text(self):
        # _is_text_file 对不存在的路径返回 False（用于目录树点击保护）。
        # 注意：.txt 等白名单扩展名会短路返回 True，故这里用非白名单扩展名。
        self.assertFalse(self.m._is_text_file(self._path("nope.xyz")))


class TestHighlight(unittest.TestCase):
    """DuckTextArea 的高亮应来自 duck_utils 的 SyntaxTokenizer。"""

    def setUp(self):
        self.m = load_mod()

    def _names(self, code, lang="python"):
        ta = self.m.DuckTextArea(duck_lang=lang)
        ta.load_text(code)
        names = set()
        for spans in ta._highlights.values():
            for start, end, name in spans:
                names.add(name)
        return names

    def test_python_tokens_highlighted(self):
        names = self._names('def f():\n    x = "hi"  # c\n', "python")
        self.assertIn("keyword", names)   # def
        self.assertIn("string", names)    # "hi"
        self.assertIn("comment", names)   # # c
        self.assertIn("operator", names)  # = 

    def test_default_lang_no_highlight(self):
        # 未识别语言时只切分文本，不产生 keyword/string/comment 高亮
        names = self._names("hello world", "default")
        self.assertEqual(names, set())


class TestApp(IsolatedAsyncioTestCase):
    """通过 Textual run_test() 无头驱动 App。"""

    async def asyncSetUp(self):
        self.m = load_mod()
        self.tmp = tempfile.mkdtemp(prefix="duck_edit_app_")

    def _write(self, name, content, enc="utf-8"):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding=enc) as fp:
            fp.write(content)
        return path

    async def test_mount_open_and_highlight(self):
        m = self.m
        p = self._write("demo.py", 'def f():\n    return "x"\n')
        app = m.DuckEditApp(start_dir=self.tmp, open_file=p)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            editor = app.query_one("#editor", m.DuckTextArea)
            self.assertEqual(editor.document.line_count, 3)
            self.assertEqual(editor._duck_lang, "python")
            names = set()
            for spans in editor._highlights.values():
                for s in spans:
                    names.add(s[2])
            self.assertIn("keyword", names)
            # 打开后 current_path 记录为所打开的文件
            self.assertEqual(app.current_path, p)

    async def test_save_writes_file(self):
        m = self.m
        p = self._write("save.py", 'print("hi")\n')
        app = m.DuckEditApp(start_dir=self.tmp, open_file=p)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            editor = app.query_one("#editor", m.DuckTextArea)
            editor.load_text('print("hello")\n')
            # 直接调用保存动作（已有路径）
            app.action_save()
            await pilot.pause()
            with open(p, "r", encoding="utf-8") as fp:
                self.assertEqual(fp.read(), 'print("hello")\n')

    async def test_goto_moves_cursor(self):
        m = self.m
        p = self._write("goto.py", "a\nb\nc\nd\n")
        app = m.DuckEditApp(start_dir=self.tmp, open_file=p)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app._on_goto("3")
            await pilot.pause()
            editor = app.query_one("#editor", m.DuckTextArea)
            self.assertEqual(editor.selection.end[0], 2)  # 第 3 行 -> row 索引 2

    async def test_quit_dirty_pushes_confirm(self):
        m = self.m
        p = self._write("dirty.py", "x\n")
        app = m.DuckEditApp(start_dir=self.tmp, open_file=p)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            editor = app.query_one("#editor", m.DuckTextArea)
            editor.load_text("x\ny\n")  # 产生未保存修改
            self.assertTrue(app._is_dirty())
            await app.action_quit()
            await pilot.pause()
            # 应弹出退出确认弹窗
            self.assertTrue(any(
                isinstance(screen, m.ConfirmQuit) for screen in app.screen_stack
            ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
