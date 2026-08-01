# encoding=utf-8

import argparse
import io
import sys
from typing import Dict, List, Literal, Optional, Tuple

from termcolor import colored
from duck_utils.syntax_util import SyntaxTokenizer, Token, detect_lang

# termcolor 的颜色/属性字面量类型
ColorName = Literal[
    "black", "grey", "red", "green", "yellow", "blue", "magenta", "cyan",
    "light_grey", "dark_grey", "light_red", "light_green", "light_yellow",
    "light_blue", "light_magenta", "light_cyan", "white",
]
AttrName = Literal["bold", "dark", "underline", "blink", "reverse", "concealed"]

# 各 token 类型的配色(针对黑色背景调校对比度)
TOKEN_COLORS = {
    "comment": ("cyan", []),
    "string": ("green", []),
    "number": ("yellow", []),
    "keyword": ("magenta", ["bold"]),
    "symbol": ("red", []),
}  # type: Dict[str, Tuple[ColorName, List[AttrName]]]

_LINE_NUMBER_COLOR = "cyan"  # type: ColorName


def color_token(tok: Token) -> str:
    """按 token 类型上色, 'text' 类型原样返回。"""
    if tok.kind == "text":
        return tok.text
    color, attrs = TOKEN_COLORS[tok.kind]
    return colored(tok.text, color, attrs=attrs)


def color_line(line: str, tokenizer: SyntaxTokenizer) -> str:
    """对单行做语法高亮, 返回上色后的文本(三引号跨行状态由 tokenizer 维护)。"""
    return "".join(color_token(t) for t in tokenizer.tokenize(line))


def cat_lines(lines, number: bool = False, highlight: bool = False,
              lang: str = "default", max_lines: int = 0) -> None:
    tokenizer = SyntaxTokenizer(lang) if highlight else None
    for index, line in enumerate(lines, 1):
        if max_lines > 0 and index > max_lines:
            break

        if highlight and tokenizer is not None:
            colored_line = color_line(line, tokenizer)
        else:
            colored_line = line

        if number:
            num = "%6d" % index
            if highlight:
                num = colored(num, _LINE_NUMBER_COLOR)
            print(num + "\t" + colored_line, end="")
        else:
            print(colored_line, end="")


def cat_stdin(number: bool = False, highlight: bool = False,
              lang: str = "default", max_lines: int = 0) -> None:
    cat_lines(sys.stdin.readlines(), number, highlight, lang, max_lines)


def _decode_file(filename: str, encoding: str) -> str:
    """鲁棒读取文件文本：依次尝试指定编码 / utf-8 / chardet 探测，
    最终回退为 utf-8 并以 errors='replace' 解码，保证对非 utf-8 文本（如
    UTF-16/GBK）也能预览，且绝不因解码失败而崩溃。"""
    with open(filename, "rb") as fb:
        data = fb.read()
    if encoding and encoding != "utf-8":
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            pass
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        import chardet
        result = chardet.detect(data)
        enc = result.get("encoding") if result else None
        if enc:
            try:
                return data.decode(enc)
            except (UnicodeDecodeError, LookupError):
                pass
    except Exception:  # noqa: chardet 探测失败不应影响预览
        pass
    return data.decode("utf-8", errors="replace")


def cat_file(filename: str = "", encoding: str = "utf-8", number: bool = False,
             highlight: bool = False, lang: str = "default",
             max_lines: int = 0) -> None:
    """读取文件内容, 用于 windows 环境模拟 cat 命令。"""
    if filename == "":
        cat_stdin(number, highlight, lang, max_lines)
        return

    # 终端编码（如 Windows GBK）无法表示某些字符时，以替换符兜底，避免打印时崩溃
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(errors="replace")

    if highlight and lang == "default":
        lang = detect_lang(filename)

    text = _decode_file(filename, encoding)
    # 归一化换行符：Windows 文件多为 \r\n，而 _decode_file 读原始字节不做换行转换，
    # 否则 print 在 Windows 下会把行尾 \n 再翻译成 \r\n，产生 \r\r\n 双回车（表现为多余空行）
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    cat_lines(io.StringIO(text).readlines(), number, highlight, lang, max_lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="读取文件内容并输出(模拟 cat)。支持行号与语法高亮。")
    parser.add_argument("filename", type=str, nargs="?", default="",
                        help="要输出的文件路径, 留空则从标准输入读取")
    parser.add_argument("--encoding", type=str, default="utf-8",
                        help="文件编码, 默认 utf-8")
    parser.add_argument("-n", "--number", action="store_true",
                        help="对输出的所有行加上行号(类似 cat -n)")
    parser.add_argument("-H", "--highlight", action="store_true",
                        help="启用语法高亮: 关键字/字符串/注释/数字/特殊符号/行号分色显示")
    parser.add_argument("--lang", type=str, default="",
                        help="指定高亮语言(如 python/js/c/go/sql...)，"
                             "留空时按扩展名自动推断")
    parser.add_argument("-L", "--max-lines", type=int, default=0,
                        help="限制输出的最大行数, 0 或不传表示不限制(类似 head -n)")
    args = parser.parse_args()

    lang = args.lang if args.lang else "default"
    cat_file(args.filename, args.encoding, args.number, args.highlight, lang,
             args.max_lines)
