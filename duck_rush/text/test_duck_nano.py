# -*- coding: utf-8 -*-
"""duck-nano 单元测试。

直接运行:  python duck_rush/text/test_duck_nano.py

内部函数（编解码 / 纯文本操作 / 语法高亮）通过 importlib 直接加载模块测试;
CLI 行为（主要是 -h 无副作用）通过子进程运行 duck-nano.py 做端到端验证。
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "duck-nano.py")


def load_mod():
    """以 importlib 加载带连字符的脚本模块。"""
    spec = importlib.util.spec_from_file_location("duck_nano_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(args, stdin_text=""):
    """运行 CLI 并返回 (returncode, stdout, stderr)。"""
    proc = subprocess.run(
        [sys.executable, SCRIPT] + args,
        input=stdin_text, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


class TestCodec(unittest.TestCase):
    """编码 / 换行符的读写应原样保留。"""

    def setUp(self):
        self.m = load_mod()
        self.tmp = tempfile.mkdtemp(prefix="duck_nano_")

    def _path(self, name):
        return os.path.join(self.tmp, name)

    def test_explicit_encoding_roundtrip(self):
        m = self.m
        cases = ["utf-8", "gbk", "utf-8-sig", "utf-16"]
        for enc in cases:
            with self.subTest(enc=enc):
                src = "中文 abc 123\n".encode(enc)
                path = self._path("rt_%s.txt" % enc)
                with open(path, "wb") as fp:
                    fp.write(src)
                doc = m.load_file(path, encoding=enc)
                # 换行符统一为 \n，文本应与解码结果一致
                self.assertEqual(doc.text, src.decode(enc).replace("\r\n", "\n").replace("\r", "\n"))
                self.assertEqual(doc.encoding, enc)
                # 保存后字节完全一致（编码 + 换行符原样写回）
                out = self._path("out_%s.txt" % enc)
                m.save_file(out, doc.text, doc)
                with open(out, "rb") as fp:
                    self.assertEqual(fp.read(), src)

    def test_bom_utf8sig_detected_and_stripped(self):
        m = self.m
        src = "x = 1\n".encode("utf-8-sig")  # 带 BOM
        path = self._path("bom.txt")
        with open(path, "wb") as fp:
            fp.write(src)
        doc = m.load_file(path)  # 自动探测
        self.assertEqual(doc.encoding, "utf-8-sig")
        self.assertNotIn("\ufeff", doc.text)
        self.assertNotIn("\r", doc.text)

    def test_newline_crlf_roundtrip(self):
        m = self.m
        src = b"a\r\nb\r\n"
        path = self._path("crlf.txt")
        with open(path, "wb") as fp:
            fp.write(src)
        doc = m.load_file(path)
        self.assertEqual(doc.newline, "\r\n")
        self.assertEqual(doc.text, "a\nb\n")
        out = self._path("out_crlf.txt")
        m.save_file(out, doc.text, doc)
        with open(out, "rb") as fp:
            self.assertEqual(fp.read(), src)

    def test_newline_lf_roundtrip(self):
        m = self.m
        src = b"a\nb\n"
        path = self._path("lf.txt")
        with open(path, "wb") as fp:
            fp.write(src)
        doc = m.load_file(path)
        self.assertEqual(doc.newline, "\n")
        out = self._path("out_lf.txt")
        m.save_file(out, doc.text, doc)
        with open(out, "rb") as fp:
            self.assertEqual(fp.read(), src)

    def test_load_missing_file_is_empty_buffer(self):
        m = self.m
        path = self._path("does_not_exist.txt")
        doc = m.load_file(path)
        self.assertFalse(doc.exists)
        self.assertEqual(doc.text, "")

    def test_autodetect_gbk_roundtrip_preserves_text(self):
        """无显式编码时 chardet 自动探测，往返后文本应保持一致。"""
        m = self.m
        src = "中文内容\n另一行\n".encode("gbk")
        path = self._path("auto_gbk.txt")
        with open(path, "wb") as fp:
            fp.write(src)
        doc = m.load_file(path)
        self.assertTrue(doc.encoding)  # 探测到了某种编码
        # 重存后用同一编码再读，文本应等价
        out = self._path("auto_gbk_out.txt")
        m.save_file(out, doc.text, doc)
        reloaded = m.load_file(out, encoding=doc.encoding)
        self.assertEqual(reloaded.text, doc.text)


class TestPureLogic(unittest.TestCase):
    """与界面无关的纯文本操作。"""

    def setUp(self):
        self.m = load_mod()

    def test_find_next_finds_and_wraps(self):
        m = self.m
        text = "hello world hello"
        # 从第二个匹配之后开始，应环绕回开头
        self.assertEqual(m.find_next(text, "hello", 13), 0)
        # 正常命中
        self.assertEqual(m.find_next(text, "hello", 7), 12)
        # 不存在
        self.assertIsNone(m.find_next(text, "xyz", 0))

    def test_find_next_case_sensitivity(self):
        m = self.m
        self.assertEqual(m.find_next("Hello", "hello", 0, ignore_case=True), 0)
        self.assertIsNone(m.find_next("Hello", "hello", 0, ignore_case=False))

    def test_replace_all_counts_and_preserves_case(self):
        m = self.m
        new, count = m.replace_all("aXaXa", "x", "Y")
        self.assertEqual(new, "aYaYa")
        self.assertEqual(count, 2)
        # 大小写不敏感：命中数正确
        new, count = m.replace_all("Hello hello", "hello", "hi", ignore_case=True)
        self.assertEqual(new, "hi hi")
        self.assertEqual(count, 2)
        # old 为空直接返回
        self.assertEqual(m.replace_all("abc", "", "z"), ("abc", 0))

    def test_cut_line_basic(self):
        m = self.m
        text = "abc\ndef\nghi"
        new, cursor, cut = m.cut_line(text, 1)  # 光标在第一行
        self.assertEqual(new, "def\nghi")
        self.assertEqual(cursor, 0)
        self.assertEqual(cut, "abc\n")

    def test_cut_line_last_line_no_trailing_newline(self):
        m = self.m
        text = "abc\ndef"
        new, cursor, cut = m.cut_line(text, 5)  # 光标在末行 "def"
        self.assertEqual(new, "abc\n")
        self.assertEqual(cursor, 4)
        self.assertEqual(cut, "def")

    def test_cut_line_empty_text(self):
        m = self.m
        new, cursor, cut = m.cut_line("", 0)
        self.assertEqual(new, "")
        self.assertEqual(cursor, 0)
        self.assertEqual(cut, "")

    def test_line_col(self):
        m = self.m
        text = "ab\ncde\nf"
        self.assertEqual(m.line_col(text, 0), (1, 1))   # 'a' 行1列1
        self.assertEqual(m.line_col(text, 2), (1, 3))   # "ab" 行尾
        self.assertEqual(m.line_col(text, 3), (2, 1))   # 第二行开头 'c'
        self.assertEqual(m.line_col(text, 5), (2, 3))   # 第二行 'e'
        self.assertEqual(m.line_col(text, 8), (3, 2))   # 第三行 'f'

    def test_line_start_offset(self):
        m = self.m
        text = "ab\ncde\nf"
        self.assertEqual(m.line_start_offset(text, 1), 0)
        self.assertEqual(m.line_start_offset(text, 2), 3)
        self.assertEqual(m.line_start_offset(text, 3), 7)
        # 越界钳制
        self.assertEqual(m.line_start_offset(text, 99), 7)
        self.assertEqual(m.line_start_offset(text, 0), 0)


class TestLexer(unittest.TestCase):
    """DuckLexer 必须支持乱序取行（prompt_toolkit 可能乱序渲染）。"""

    def setUp(self):
        self.m = load_mod()

    def _get_line(self, source, lineno, lang="python"):
        m = self.m
        from prompt_toolkit.document import Document
        doc = Document(source)
        lexer = m.DuckLexer(lang)
        get_line = lexer.lex_document(doc)
        return get_line(lineno)

    def test_out_of_order_fetch_matches_in_order(self):
        m = self.m
        source = "# comment\nx = 1\nprint('hi')\n"
        from prompt_toolkit.document import Document
        lexer = m.DuckLexer("python")
        get_line = lexer.lex_document(Document(source))
        in_order = [get_line(i) for i in range(len(source.splitlines()))]
        # 打乱顺序取行，结果应与顺序取行一致（跨行状态由游标维护）
        scrambled = [get_line(2), get_line(0), get_line(1), get_line(2), get_line(0)]
        self.assertEqual(scrambled[0], in_order[2])
        self.assertEqual(scrambled[1], in_order[0])
        self.assertEqual(scrambled[2], in_order[1])
        # 所有返回都是 StyleAndTextTuples（list of (style, text)）
        for frag in in_order:
            self.assertIsInstance(frag, list)
            for style, text in frag:
                self.assertIsInstance(style, str)
                self.assertIsInstance(text, str)

    def test_python_comment_tokenized(self):
        m = self.m
        frag = self._get_line("# this is a comment\n", 0, lang="python")
        joined = "".join(text for _, text in frag)
        self.assertEqual(joined, "# this is a comment")
        # 注释应带 token.comment 样式
        self.assertTrue(any(style == "class:token.comment" for style, _ in frag))

    def test_string_tokenized(self):
        m = self.m
        frag = self._get_line("s = 'hello'\n", 0, lang="python")
        self.assertTrue(any(style == "class:token.string" for style, _ in frag))

    def test_line_out_of_range_returns_empty(self):
        m = self.m
        frag = self._get_line("a\nb\n", 99, lang="python")
        self.assertEqual(frag, [])


class TestCLI(unittest.TestCase):
    """端到端验证命令行行为（重点：-h 必须无副作用）。"""

    def test_help_no_side_effect(self):
        # -h 应在解析任何参数前退出，绝不触碰文件名参数指向的文件
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "should_not_be_created.txt")
            rc, out, err = run(["-h", target])
            self.assertEqual(rc, 0)
            self.assertIn("duck-nano", out)
            self.assertFalse(os.path.exists(target),
                             "-h 不应创建任何文件")

    def test_help_stdout_is_docstring(self):
        rc, out, _ = run(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("快捷键", out)
        self.assertIn("用法", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
