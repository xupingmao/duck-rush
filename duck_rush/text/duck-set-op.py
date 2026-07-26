# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/07/26
# @filename duck-set-op.py
# @description 集合运算工具: 支持并集/交集/差集/对称差(union/intersection/difference/symmetric)

import sys
from typing import Dict, List, Optional, Set

USAGE = (
    "集合运算工具: 对一个或多个文本文件做集合运算, 每个文件每行是一个集合元素。\n"
    "用法: duck-set-op -o <op> [-s] [--keep-empty] [--encoding ENC] file1 [file2 ...]\n"
    "  -o, --op       运算类型: union(并集) | difference/diff/sub(差集) | intersection/and/intersect(交集) | symmetric/xor(对称差)\n"
    "  file           输入文件, 每行一个元素; 可用 - 表示从标准输入读取\n"
    "  -s, --strip    去除每个元素两端的空白字符后再比较(默认已去除行尾空白)\n"
    "  --keep-empty   默认会跳过空行, 加此选项则保留空行作为元素\n"
    "  --encoding     文件编码, 默认 utf-8\n"
)


# --op 的别名映射: 别名 -> 规范运算名
OP_ALIASES = {
    "union": "union",
    "difference": "difference",
    "diff": "difference",
    "sub": "difference",
    "intersection": "intersection",
    "and": "intersection",
    "intersect": "intersection",
    "symmetric": "symmetric",
    "xor": "symmetric",
}


def parse_op(value: str) -> str:
    """将 --op 的取值(支持别名)归一为规范运算名, 非法取值报错。"""
    canonical = OP_ALIASES.get(value)
    if canonical is None:
        raise ValueError(
            "未知运算: %s (可选: union, difference/diff/sub, "
            "intersection/and/intersect, symmetric/xor)" % value
        )
    return canonical


def read_elements(path: str, strip: bool, keep_empty: bool,
                  encoding: str) -> List[str]:
    """读取单个文件(或 stdin), 返回按出现顺序去重后的元素列表。

    参数:
        path:        文件路径, 为 '-' 时从标准输入读取
        strip:       是否去除每个元素两端的空白
        keep_empty:  是否保留空行作为元素
        encoding:    文件编码
    """
    if path == "-":
        lines = sys.stdin.readlines()
    else:
        with open(path, encoding=encoding) as fp:
            lines = fp.readlines()

    seen: Set[str] = set()
    result: List[str] = []
    for raw in lines:
        # 默认去除行尾换行符及多余空白(空格/制表符/回车), 避免肉眼相同的行
        # 因不可见字符而被当成不同元素; 仅保留前导空白以区分有意前置空格的内容。
        elem = raw.rstrip()
        if strip:
            elem = elem.strip()
        if elem == "" and not keep_empty:
            continue
        if elem not in seen:
            seen.add(elem)
            result.append(elem)
    return result


def ordered_union(lists: List[List[str]]) -> List[str]:
    """按全局首次出现顺序合并多个有序列表(去重)。"""
    seen: Set[str] = set()
    out: List[str] = []
    for lst in lists:
        for elem in lst:
            if elem not in seen:
                seen.add(elem)
                out.append(elem)
    return out


def apply_op(op: str, lists: List[List[str]]) -> List[str]:
    """对多个有序集合列表执行指定运算, 返回结果元素列表(保持顺序)。"""
    if not lists:
        return []

    if op == "union":
        return ordered_union(lists)

    if op == "difference":
        # 第一个集合减去其余集合的并集
        if len(lists) == 1:
            return list(lists[0])
        rest: Set[str] = set()
        for lst in lists[1:]:
            rest.update(lst)
        return [elem for elem in lists[0] if elem not in rest]

    # intersection / symmetric 需要"出现在所有集合"或"出现奇数次"的成员集合
    if op == "intersection":
        common: Set[str] = set(lists[0])
        for lst in lists[1:]:
            common &= set(lst)
        ordered = ordered_union(lists)
        return [elem for elem in ordered if elem in common]

    if op == "symmetric":
        sym: Set[str] = set(lists[0])
        for lst in lists[1:]:
            sym ^= set(lst)
        ordered = ordered_union(lists)
        return [elem for elem in ordered if elem in sym]

    raise ValueError("未知运算: %s" % op)


def main() -> None:
    # 显式处理 -h/--help, 保证 duck list / install 提取简介且无副作用
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        sys.stdout.write(USAGE)
        sys.exit(0)

    import argparse

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="集合运算工具: 对一个或多个文本文件做并集/交集/差集/对称差运算")
    parser.add_argument("-o", "--op", type=parse_op, required=True,
                        help="运算类型: union | difference(diff/sub) | "
                             "intersection(and/intersect) | symmetric(xor)")
    parser.add_argument("-s", "--strip", action="store_true",
                        help="去除每个元素两端的空白字符后再比较(默认仅去行尾空白)")
    parser.add_argument("--keep-empty", action="store_true",
                        help="保留空行作为元素(默认跳过空行)")
    parser.add_argument("--encoding", type=str, default="utf-8",
                        help="文件编码, 默认 utf-8")
    parser.add_argument("files", type=str, nargs="+",
                        help="输入文件, 每行一个元素; 可用 - 表示标准输入")
    args: argparse.Namespace = parser.parse_args()

    lists: List[List[str]] = [
        read_elements(path, args.strip, args.keep_empty, args.encoding)
        for path in args.files
    ]
    result: List[str] = apply_op(args.op, lists)
    sys.stdout.write("".join(elem + "\n" for elem in result))


if __name__ == "__main__":
    main()
