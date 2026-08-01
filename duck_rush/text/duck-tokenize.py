# -*- coding: utf-8 -*-
"""
duck-tokenize —— 调用 duck_utils 的语法分词器，对文本 / 文件做分词。

接受文件参数或管道(stdin)输入; 默认按扩展名自动推断语言，也可用 --lang 显式指定。
每行独立分词，但共享同一个 SyntaxTokenizer 实例，以跨行保持三引号字符串 /
块注释的状态; 输出每个 token 的 (类型, 文本)。

用法:
  duck-tokenize [文件] [--lang LANG] [--format jsonl|text] [-h]
  cat file.py | duck-tokenize --lang python

说明:
  - 未指定文件或文件为 '-' 时读取 stdin。
  - 默认输出 JSONL(每行一个 {"kind":..., "text":...})，便于后续管道处理;
    --format text 则输出 "类型<TAB>文本"。
  -h/--help 必须无副作用（不读写文件、不进入 TUI），放 main 最开头直接退出。
"""
import argparse
import json
import os
import sys
from typing import List, Optional, Tuple

from duck_utils.syntax_util import SyntaxTokenizer, Token, detect_lang


def _read_input(path: Optional[str]) -> str:
    """读取输入文本：path 为 None 或 '-' 时读 stdin，否则读文件。

    解码顺序 utf-8 -> gbk -> latin-1（兜底）。
    """
    if not path or path == "-":
        data = sys.stdin.buffer.read()
    else:
        with open(path, "rb") as fp:
            data = fp.read()
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _detect_lang_for(path: Optional[str], lang: Optional[str]) -> str:
    """确定分词语言：显式 --lang 优先，其次按文件扩展名，最后 'default'。"""
    if lang:
        return lang
    if path and path != "-":
        return detect_lang(path)
    return "default"


def tokenize_text(text: str, lang: str) -> "List[Token]":
    """按行分词（共享分词器以跨行保持三引号 / 块注释状态），返回 token 列表。

    逐行调用是为了让行注释只作用到行尾（分词器对整段文本会把行注释吞到 EOF）。
    """
    tokenizer = SyntaxTokenizer(lang)
    result: List[Token] = []
    for line in text.split("\n"):
        result.extend(tokenizer.tokenize(line))
    return result


def _emit(tokens: "List[Token]", fmt: str) -> None:
    out = sys.stdout
    if fmt == "text":
        for tok in tokens:
            out.write("%s\t%s\n" % (tok.kind, tok.text))
    else:
        for tok in tokens:
            out.write(json.dumps({"kind": tok.kind, "text": tok.text},
                                 ensure_ascii=False) + "\n")


def main() -> None:
    # -h/--help 必须无副作用，放最开头直接退出
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="调用 duck_utils 的语法分词器对文本/文件分词",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", nargs="?", default=None,
                        help="输入文件(默认读 stdin；'-' 也表 stdin)")
    parser.add_argument("--lang", default=None,
                        help="显式指定语言(默认按扩展名推断，如 python/js/go/...）")
    parser.add_argument("--format", choices=("jsonl", "text"), default="jsonl",
                        help="输出格式：jsonl(默认) 或 text(类型<TAB>文本)")
    args = parser.parse_args()

    text = _read_input(args.file)
    lang = _detect_lang_for(args.file, args.lang)
    _emit(tokenize_text(text, lang), args.format)


if __name__ == "__main__":
    main()
