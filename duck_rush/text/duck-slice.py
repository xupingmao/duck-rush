# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2024/01/01
# @filename duck-slice.py
# @description 对输入按行切片, 语法类似 Python 的切片 slice[start:stop:step]

import sys
import io
import argparse


def ensure_utf8_output():
    """强制以 UTF-8 输出, 避免 Windows 控制台代码页导致的中文乱码"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def parse_slice(expr: str) -> slice:
    """解析 Python 风格的切片表达式, 支持 ``start:stop:step`` 形式。

    各部分均可省略(空串表示 None): ``"1:10"`` ``":-3"`` ``"::2"``
    ``"::-1"``, 也允许包一层方括号如 ``"[1:10]"``。
    """
    expr = expr.strip()
    if expr.startswith("[") and expr.endswith("]"):
        expr = expr[1:-1]
    if expr == "":
        raise ValueError("切片表达式不能为空")

    parts = expr.split(":")
    if len(parts) > 3:
        raise ValueError("切片最多包含 start:stop:step 三段, 收到: %r" % expr)

    nums = []
    for p in parts:
        if p == "":
            nums.append(None)
        else:
            nums.append(int(p))
    while len(nums) < 3:
        nums.append(None)
    return slice(nums[0], nums[1], nums[2])


def slice_text(text: str, sl: slice) -> str:
    """将文本按行切片后重新拼接, 保留原始行尾换行。"""
    lines = text.splitlines(keepends=True)
    selected = lines[sl]
    return "".join(selected)


def main():
    parser = argparse.ArgumentParser(
        description="对输入按行切片, 语法类似 Python 的 slice[start:stop:step]")
    parser.add_argument("slice_expr", metavar="SLICE",
                        help="切片表达式, 如 1:10 / :-3 / ::2 / ::-1")
    parser.add_argument("filename", nargs="?", default="",
                        help="可选的输入文件, 未指定则从标准输入读取")
    parser.add_argument("-E", "--encoding", default="utf-8",
                        help="输入内容的编码(默认 utf-8, GBK 文件可传 gbk)")
    args = parser.parse_args()

    ensure_utf8_output()

    sl = parse_slice(args.slice_expr)

    if args.filename:
        with open(args.filename, encoding=args.encoding, errors="replace") as fp:
            text = fp.read()
    else:
        data = sys.stdin.buffer.read()
        text = data.decode(args.encoding, errors="replace")

    sys.stdout.write(slice_text(text, sl))


if __name__ == '__main__':
    main()
