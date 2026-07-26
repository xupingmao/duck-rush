# -*- coding: utf-8 -*-
"""duck_utils.syntax_util 单元测试 + duck-cat 最大行数参数测试。

直接运行:  python duck_rush/text/test_syntax_util.py
"""

import importlib.util
import io
import os
import sys
import unittest

# 优先测试本地源码(而非可能过期的 egg)
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from duck_utils.syntax_util import (  # noqa: E402
    SyntaxTokenizer,
    Token,
    TOKEN_KINDS,
    detect_lang,
    tokenize,
)

DUCK_CAT = os.path.join(HERE, "duck-cat.py")


def load_duck_cat():
    """以 importlib 加载带连字符的 duck-cat 脚本模块。"""
    spec = importlib.util.spec_from_file_location("duck_cat_test", DUCK_CAT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cat_lines_capture(mod, lines, number=False, highlight=False,
                      lang="default", max_lines=0):
    """调用 duck-cat 的 cat_lines 并捕获 stdout 输出。"""
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        mod.cat_lines(list(lines), number, highlight, lang, max_lines)
    finally:
        sys.stdout = old
    return buf.getvalue()


class TestDetectLang(unittest.TestCase):

    def test_known_extensions(self):
        self.assertEqual(detect_lang("a.py"), "python")
        self.assertEqual(detect_lang("a.ts"), "typescript")
        self.assertEqual(detect_lang("a.go"), "go")
        self.assertEqual(detect_lang("a.sql"), "sql")

    def test_unknown_and_empty(self):
        self.assertEqual(detect_lang("a.unknown"), "default")
        self.assertEqual(detect_lang("noext"), "default")
        self.assertEqual(detect_lang(""), "default")


class TestTokenize(unittest.TestCase):

    def test_returns_tokens(self):
        toks = list(tokenize('def f(): pass', "python"))
        self.assertTrue(toks)
        for t in toks:
            self.assertIsInstance(t, Token)
            self.assertIn(t.kind, TOKEN_KINDS)

    def test_python_kinds(self):
        kinds = [t.kind for t in tokenize('def foo(x):  # c', "python")]
        self.assertIn("keyword", kinds)
        self.assertIn("comment", kinds)
        self.assertIn("symbol", kinds)
        self.assertIn("text", kinds)

    def test_string_and_number(self):
        kinds = [t.kind for t in tokenize('s = "hi"; n = 42', "python")]
        self.assertIn("string", kinds)
        self.assertIn("number", kinds)

    def test_symbols(self):
        kinds = [t.kind for t in tokenize("a + b * (c - 1)", "python")]
        self.assertIn("symbol", kinds)
        self.assertIn("number", kinds)

    def test_single_quoted_containing_triple(self):
        # 修复: 普通字符串内部的 """ 不应被误判为三引号边界
        toks = list(tokenize("'\"\"\"'", "python"))
        self.assertEqual([(t.kind, t.text) for t in toks], [("string", "'\"\"\"'")])

    def test_triple_inside_double_string_not_split(self):
        # 双引号字符串内部用转义包含三个双引号, 整体应是一个 string 而非被拆成三引号边界
        s = '"' + '\\"' * 3 + '"'  # 形如 "\"\""\"
        toks = list(tokenize(s, "python"))
        self.assertEqual([(t.kind, t.text) for t in toks], [("string", s)])

    def test_block_comment_spanning_lines(self):
        tk = SyntaxTokenizer("c")
        out = []
        for line in ["/* a\n", "b */ x = 1\n"]:
            out.extend((t.kind, t.text) for t in tk.tokenize(line))
        self.assertIn(("comment", "/* a\n"), out)
        self.assertIn(("comment", "b */"), out)
        self.assertIn(("number", "1"), out)

    def test_default_lang_no_keyword_or_comment(self):
        # default 规则不识别关键字/注释, 但仍切分字符串/数字/符号
        kinds = [t.kind for t in tokenize('def x = "hi" # note', "default")]
        self.assertNotIn("keyword", kinds)
        self.assertNotIn("comment", kinds)
        self.assertIn("string", kinds)
        self.assertIn("symbol", kinds)

    def test_roundtrip_python(self):
        text = 'def foo(x):\n    s = "hello"  # inline\n    return x * 2\n'
        self.assertEqual("".join(t.text for t in tokenize(text, "python")), text)

    def test_roundtrip_javascript(self):
        text = 'const x = "hi"; // c\nfunction f() { return 1; }\n'
        self.assertEqual("".join(t.text for t in tokenize(text, "javascript")), text)

    def test_roundtrip_c_block_comment(self):
        text = 'int x = 1; /* block\ncomment */ y = 2;\n'
        self.assertEqual("".join(t.text for t in tokenize(text, "c")), text)

    def test_token_kinds_complete(self):
        self.assertEqual(TOKEN_KINDS,
                         {"comment", "string", "number", "keyword", "symbol", "text"})


class TestTripleQuote(unittest.TestCase):

    def test_one_shot_spanning_text(self):
        text = '"""multi\nline\nbody""" x = 1'
        toks = list(tokenize(text, "python"))
        self.assertEqual("".join(t.text for t in toks), text)
        # 三引号内部整体为 string
        joined = "".join(t.text for t in toks if t.kind == "string")
        self.assertIn('"""multi\nline\nbody"""', joined)
        # 结束后恢复普通分词
        kinds = [t.kind for t in toks]
        self.assertIn("number", kinds)

    def test_streaming_cross_line_state(self):
        tk = SyntaxTokenizer("python")
        collected = []
        for line in ['"""multi\n', 'body\n', 'end""" x = 1\n']:
            collected.extend(tokenize_line_kind(tk, line))
        self.assertIn(("string", '"""multi\n'), collected)
        self.assertIn(("string", "body\n"), collected)
        self.assertIn(("string", 'end"""'), collected)
        # 三引号关闭后, 后续标识符/数字正常分词
        self.assertIn(("number", "1"), collected)

    def test_unterminated_triple_keeps_state(self):
        tk = SyntaxTokenizer("python")
        toks = list(tk.tokenize('"""unterminated'))
        self.assertEqual([(t.kind, t.text) for t in toks],
                         [("string", '"""unterminated')])


def tokenize_line_kind(tk, line):
    return [(t.kind, t.text) for t in tk.tokenize(line)]


class TestDuckCatMaxLines(unittest.TestCase):

    def setUp(self):
        self.m = load_duck_cat()

    def test_no_limit(self):
        out = cat_lines_capture(self.m, ["l1\n", "l2\n", "l3\n"])
        self.assertEqual(out, "l1\nl2\nl3\n")

    def test_max_lines_limits(self):
        out = cat_lines_capture(self.m, ["l1\n", "l2\n", "l3\n", "l4\n"],
                                 max_lines=2)
        self.assertEqual(out, "l1\nl2\n")

    def test_max_lines_with_number(self):
        out = cat_lines_capture(self.m, ["a\n", "b\n", "c\n"], number=True,
                                 max_lines=2)
        # 行号保留原始编号
        self.assertEqual(out, "     1\ta\n     2\tb\n")

    def test_max_lines_with_highlight(self):
        out = cat_lines_capture(self.m,
                                 ['def f():\n', '    return 1\n', 'x = 2\n'],
                                 highlight=True, lang="python", max_lines=2)
        self.assertEqual(out, "def f():\n    return 1\n")

    def test_max_lines_zero_means_unlimited(self):
        out = cat_lines_capture(self.m, ["a\n", "b\n"], max_lines=0)
        self.assertEqual(out, "a\nb\n")


if __name__ == "__main__":
    unittest.main()
