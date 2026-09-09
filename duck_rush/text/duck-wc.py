# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/09/10
# @filename duck-wc.py
# @description 统计文本的行数/词数/字符数/字节数（类似 wc 命令）
"""duck-wc —— 统计文本的行数、词数、字符数、字节数。

用法:
  duck-wc [选项] [文件...]
  cat file | duck-wc [选项]

选项:
  -l, --lines      只统计行数（换行符个数）
  -w, --words      只统计词数（以空白分隔的片段）
  -c, --bytes      只统计字节数
  -m, --chars      只统计字符数（按文本解码后计数）
  --encoding NAME  读取文件时使用的编码（默认 utf-8）
  -h, --help       显示本帮助

不指定 -l/-w/-c/-m 时，默认输出 `行数 词数 字节数` 三列；
指定任意列选项后，只输出所选列。
多个文件时末尾会输出 total 汇总行。
"""

import sys
import argparse
from dataclasses import dataclass
from typing import List, Optional

CHUNK_SIZE = 65536


@dataclass
class CountResult:
    """单份输入的统计结果"""

    lines: int = 0
    words: int = 0
    chars: int = 0
    bytes: int = 0

    def add(self, other: "CountResult") -> None:
        self.lines += other.lines
        self.words += other.words
        self.chars += other.chars
        self.bytes += other.bytes


def count_stream(fp, encoding: str = "utf-8") -> CountResult:
    """分块读取并统计，避免一次性加载大文件。

    参数:
        fp:       二进制可读的文件对象
        encoding: 解码用的字符编码, 无法解码的字节按 replacement 处理
    """
    result = CountResult()
    # 跨块被截断的单词片段, 留到下一块再参与切分
    pending = ""

    while True:
        chunk = fp.read(CHUNK_SIZE)
        if not chunk:
            break

        result.bytes += len(chunk)
        text = chunk.decode(encoding, errors="replace")
        result.chars += len(text)
        result.lines += text.count("\n")

        parts = (pending + text).split()
        if text and not text[-1].isspace():
            # 末尾是单词的一部分, 可能跨块, 先不计数
            result.words += max(len(parts) - 1, 0)
            pending = parts[-1] if parts else ""
        else:
            result.words += len(parts)
            pending = ""

    if pending:
        result.words += 1

    return result


def count_file(fpath: str, encoding: str = "utf-8") -> CountResult:
    with open(fpath, "rb") as fp:
        return count_stream(fp, encoding)


def format_result(result: CountResult, columns: List[str], name: str = "") -> str:
    values = {"l": result.lines, "w": result.words,
              "c": result.bytes, "m": result.chars}
    parts = ["%d" % values[key] for key in columns]
    if name:
        parts.append(name)
    return " ".join(parts)


def resolve_columns(show_lines: bool, show_words: bool,
                    show_bytes: bool, show_chars: bool) -> List[str]:
    """根据列选项决定输出哪些列, 未指定任何列时使用默认三列"""
    columns: List[str] = []
    if show_lines:
        columns.append("l")
    if show_words:
        columns.append("w")
    if show_bytes:
        columns.append("c")
    if show_chars:
        columns.append("m")
    if not columns:
        columns = ["l", "w", "c"]
    return columns


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="统计文本的行数/词数/字符数/字节数")
    parser.add_argument("files", nargs="*", default=[],
                        help="待统计的文件, 缺省时读取标准输入")
    parser.add_argument("-l", "--lines", action="store_true", help="统计行数")
    parser.add_argument("-w", "--words", action="store_true", help="统计词数")
    parser.add_argument("-c", "--bytes", action="store_true", help="统计字节数")
    parser.add_argument("-m", "--chars", action="store_true", help="统计字符数")
    parser.add_argument("--encoding", default="utf-8",
                        help="读取文件的编码（默认 utf-8）")
    args = parser.parse_args(argv)

    columns = resolve_columns(args.lines, args.words, args.bytes, args.chars)
    total = CountResult()

    if not args.files:
        result = count_stream(sys.stdin.buffer, args.encoding)
        print(format_result(result, columns))
        return 0

    for fpath in args.files:
        try:
            result = count_file(fpath, args.encoding)
        except OSError as e:
            print("读取失败: %s (%s)" % (fpath, e), file=sys.stderr)
            continue
        total.add(result)
        print(format_result(result, columns, fpath))

    if len(args.files) > 1:
        print(format_result(total, columns, "total"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
