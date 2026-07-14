# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2023-12-23 13:16:20
LastEditors: xupingmao
LastEditTime: 2023-12-23 13:21:27
FilePath: /duck_rush/duck_rush/code/code-tools/format-json.py
Description: 从输入(可能是包含json的片段)中提取json并格式化输出
'''

import sys
import json
import argparse
import operator
from typing import Optional, List


class Config:
    debug = False

# ---------------------------------------------------------------------------
# --filter 支持: 顶层字段 + 比较运算符 组成 term, 多个 term 之间为或(OR)关系
#   - 单条: 字段 运算符 值, 如  name="test"   age > 10   age >= 18
#   - 多个 term 用 | 分隔, 如  name="test" | age > 10
#   - 也可多次使用 --filter, 如  --filter 'name="test"' --filter 'age > 10'
#   - 不支持嵌套路径 / 点号前缀 / 正则
# ---------------------------------------------------------------------------
_OP_MAP = {
    "=": operator.eq,
    "==": operator.eq,
    "!=": operator.ne,
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "gt": operator.gt,
    "<": operator.lt,
}

# 运算符按长度从长到短排列, 避免把 >= 误判为 = 或 >
_OP_SEQ = ("!=", ">=", "<=", "==", "=", ">", "<", "gt")


def _coerce_numeric(v):
    """能转成数字则转(float), 否则返回 None。bool 不视为数字。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


def _parse_value(s: str):
    """把条件右侧的字面值解析为 字符串/整数/浮点数。带引号视为字符串。"""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    try:
        if '.' in s or 'e' in s.lower():
            return float(s)
        return int(s)
    except ValueError:
        return s


def _get_field(obj, field: str):
    """取顶层字段的值, 找不到返回 None。"""
    if isinstance(obj, dict) and field in obj:
        return obj[field]
    return None


def _split_terms(expr: str):
    """按 | 切分为多个 term(OR), 忽略引号内的 |。"""
    parts:List[str] = []
    buf:List[str] = []
    in_q:Optional[str] = None
    
    i = 0
    while i < len(expr):
        c = expr[i]
        if in_q:
            buf.append(c)
            if c == in_q:
                in_q = None
        elif c in ('"', "'"):
            in_q = c
            buf.append(c)
        elif c == '|':
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(c)
        i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


class FilterTerm:
    """单条已解析的过滤条件: field op expected, 在循环外构造一次。"""

    def __init__(self, field: str, op, expected):
        self.field = field
        self.op = op                       # operator.eq / operator.gt ...
        self.expected = expected
        self.expected_num = _coerce_numeric(expected)

    def match(self, obj) -> bool:
        actual = _get_field(obj, self.field)
        if actual is None:
            return False
        na = _coerce_numeric(actual)
        if na is not None and self.expected_num is not None:
            return self.op(na, self.expected_num)
        return self.op(str(actual), str(self.expected))
    
    def __str__(self) -> str:
        return str(dict(field = self.field, op = self.op, expected = self.expected))


class FilterExpr:
    """多条 term 的或(OR)组合, 在循环外解析构造一次。"""

    def __init__(self, terms):
        self.terms = terms

    def match(self, obj) -> bool:
        return any(t.match(obj) for t in self.terms)
    
    def __str__(self) -> str:
        terms = [str(term) for term in self.terms]
        return str(dict(terms = terms))


def parse_filter_term(term_str: str) -> FilterTerm:
    """解析单条 term 字符串(字段 运算符 值)为 FilterTerm, 仅调用一次。"""
    term = term_str.strip()
    in_q = None
    for i, ch in enumerate(term):
        if in_q:
            if ch == in_q:
                in_q = None
            continue
        if ch in ('"', "'"):
            in_q = ch
            continue
        for op in _OP_SEQ:
            if term[i:i + len(op)] == op:
                field = term[:i].strip()
                value = term[i + len(op):].strip()
                if not field or not value:
                    raise ValueError("无法解析过滤条件: %s" % term)
                return FilterTerm(field, _OP_MAP[op], _parse_value(value))
    raise ValueError("无法解析过滤条件: %s" % term)


def build_filter(filter_arg: str) -> Optional[FilterExpr]:
    """把 --filter 参数列表(每个可含 | 分隔的多个 term)解析为 FilterExpr。"""
    if not filter_arg:
        return None
    term_strs = _split_terms(filter_arg)
    if not term_strs:
        return None
    
    if Config.debug:
        print(f"DEBUG: term_strs={term_strs}")
        
    return FilterExpr([parse_filter_term(t) for t in term_strs])


def match_filter(obj, filter_obj: FilterExpr) -> bool:
    """对单个对象执行过滤(过滤结构已预先解析好)。"""
    return filter_obj.match(obj)


def extract_segments(text: str):
    """从文本中提取所有顶层 JSON(对象或数组)以及它们之间的非 JSON 文本。

    每个片段为一个元组 ``(kind, value)``:
    - ``("json", obj)``: 解析出的 JSON 对象/数组
    - ``("text", str)``: JSON 之间的原始非 JSON 文本

    找到每个 `{`/`[` 起始位置, 用 JSONDecoder.raw_decode 尝试解析:
    解析成功则记录结果并从其后的位置继续找下一个 JSON; 失败则跳过一个字符继续。

    输入可以是纯 JSON, 也可以是在前后夹杂其它文字的片段,
    例如日志行 `xxx {"a":1} yyy ["b"] end`。
    """
    decoder = json.JSONDecoder()
    segments = []
    i = 0
    n = len(text)
    while i < n:
        # 找到下一个 JSON 起始字符 `{` 或 `[` 的最早出现位置
        pos = -1
        for ch in ('{', '['):
            idx = text.find(ch, i)
            if idx != -1 and (pos == -1 or idx < pos):
                pos = idx

        if pos == -1:
            break

        try:
            obj, end = decoder.raw_decode(text, pos)
        except ValueError:
            # 此处不是合法 JSON, 跳过一个字符继续往后找
            i = pos + 1
            continue

        if pos > i:
            segments.append(("text", text[i:pos]))
        segments.append(("json", obj))
        i = end

    if i < n:
        segments.append(("text", text[i:]))
    return segments


class JsonFormatter:
    """管理格式化的上下文选项, 并提供拍平/序列化/输出等能力。

    各选项含义:
    - compact: 一行展示一个 JSON(否则美化, 每个 JSON 之间空一行)
    - sort_keys: 按 key 排序输出
    - keep_text: 保留并原样输出 JSON 之间的非 JSON 文本
    - flat: 将嵌套 JSON 拍平为用 ``sep`` 连接的单层 dict 再输出
    - sep: 拍平时连接 key 的分隔符, 默认 ``.``
    - split: 顶层 JSON 为数组时, 将每个元素拆成独立的 JSON 输出
    - fields: 仅输出指定的字段(支持用 ``sep`` 连接的嵌套路径, 多个用逗号分隔)
    """

    def __init__(self, compact: bool = False, sort_keys: bool = False,
                 keep_text: bool = False, flat: bool = False, sep: str = ".",
                 split: bool = False, fields: list = None):
        self.compact = compact
        self.sort_keys = sort_keys
        self.keep_text = keep_text
        self.flat = flat
        self.sep = sep
        self.split = split
        self.fields = fields or []

    def _build_wanted(self) -> dict:
        """将字段列表(支持点号嵌套)构建成嵌套的 wanted 结构。

        例如 ``["a", "b.c"]`` -> ``{"a": {}, "b": {"c": {}}}``
        空 dict 表示该路径为叶子, 取该 key 对应的值; 非空表示还需继续向下筛选。
        """
        wanted = {}
        for field in self.fields:
            cur = wanted
            for part in field.split(self.sep):
                cur = cur.setdefault(part, {})
        return wanted

    def pick(self, obj: object, wanted: dict = None) -> object:
        """按 wanted 结构从 obj 中挑选出指定字段, 保留原有嵌套层级。

        - 仅挑选 dict 中命中的 key, 其它 key 丢弃
        - list 会对每个元素递归应用同样的筛选
        - obj 为标量时原样返回
        """
        if wanted is None:
            wanted = self._build_wanted()
        if isinstance(obj, dict):
            result = {}
            for k, sub in wanted.items():
                if k in obj:
                    result[k] = self.pick(obj[k], sub) if sub else obj[k]
            return result
        elif isinstance(obj, list):
            return [self.pick(item, wanted) for item in obj]
        return obj

    def flatten(self, obj: object, prefix: str = "", result: dict = None):
        """将嵌套的 dict/list 拍平为单层 dict, key 用 ``sep`` 连接。

        - dict 的嵌套值用分隔符连接, 如 ``{"a": {"b": 1}}`` -> ``{"a.b": 1}``
        - list 的元素用数字下标连接, 如 ``{"a": [1, 2]}`` -> ``{"a.0": 1}``
        - 空 dict/list 会被保留为原值, 避免丢失 key
        """
        if result is None:
            result = {}
        if isinstance(obj, dict):
            if not obj:
                result[prefix] = {}
                return result
            for k, v in obj.items():
                key = "{}{}{}".format(prefix, self.sep, k) if prefix else str(k)
                self.flatten(v, key, result)
        elif isinstance(obj, list):
            if not obj:
                result[prefix] = []
                return result
            for i, v in enumerate(obj):
                key = "{}{}{}".format(prefix, self.sep, i) if prefix else str(i)
                self.flatten(v, key, result)
        else:
            result[prefix] = obj
        return result

    def dumps(self, value: object) -> str:
        """将单个 JSON 值按上下文选项序列化为字符串。"""
        if self.fields:
            value = self.pick(value)
        if self.flat:
            value = self.flatten(value)
        indent = None if self.compact else "  "
        return json.dumps(value, ensure_ascii=False, sort_keys=self.sort_keys,
                          indent=indent)

    def format_text(self, text: str, filter_obj=None):
        """提取并格式化输出 JSON。若指定 filter_obj(已解析的过滤结构)则只输出匹配的对象。"""
        segments = extract_segments(text)
        if not segments:
            raise ValueError("未从输入中解析出任何 JSON")

        if filter_obj is not None:
            out_blocks = []
            for kind, value in segments:
                if kind != "json":
                    continue
                if isinstance(value, list) and not self.split:
                    # 顶层数组: 过滤元素后整体作为一个数组输出
                    kept = [item for item in value
                            if match_filter(item, filter_obj)]
                    if kept:
                        out_blocks.append(self.dumps(kept))
                else:
                    candidates = value if (self.split
                                           and isinstance(value, list)) else [value]
                    for item in candidates:
                        if match_filter(item, filter_obj):
                            out_blocks.append(self.dumps(item))
            if out_blocks:
                joiner = "\n" if self.compact else "\n\n"
                print(joiner.join(out_blocks))
            return

        # 每个 json 片段对应的若干 json 块(数组拆分时一个片段对应多块)
        blocks_per_segment = []
        for kind, value in segments:
            if kind != "json":
                continue
            if self.split and isinstance(value, list):
                blocks = [self.dumps(item) for item in value]
            else:
                blocks = [self.dumps(value)]
            blocks_per_segment.append(blocks)

        json_blocks = [b for blocks in blocks_per_segment for b in blocks]
        if not json_blocks:
            raise ValueError("未从输入中解析出任何 JSON")

        if not self.keep_text:
            joiner = "\n" if self.compact else "\n\n"
            print(joiner.join(json_blocks))
            return

        # keep_text=True: 按原文顺序, 将格式化后的 JSON 与原始文本交织输出
        out = []
        seg_idx = 0
        for kind, value in segments:
            if kind == "json":
                out.extend(blocks_per_segment[seg_idx])
                seg_idx += 1
            else:
                out.append(value)
        print("".join(out))


def format_json():
    """格式化json并展示: 默认美化, 可用 --compact 改为一行一个json"""
    parser = argparse.ArgumentParser(
        description="格式化 JSON: 默认美化展示, 支持从含 JSON 的片段中提取")
    parser.add_argument("filename", nargs="?", default="",
                        help="可选的输入文件, 未指定则从标准输入读取")
    parser.add_argument("-c", "--compact", action="store_true",
                        help="一行展示一个 JSON(紧凑模式)")
    parser.add_argument("-s", "--sort-keys", action="store_true",
                        help="按 key 排序输出(默认不排序, 与美化保持一致)")
    parser.add_argument("-k", "--keep-text", action="store_true",
                        help="保留并原样输出 JSON 之间的非 JSON 文本内容")
    parser.add_argument("-f", "--flat", action="store_true",
                        help="将嵌套 JSON 拍平为点号连接的单层 dict 再输出")
    parser.add_argument("-S", "--split", action="store_true",
                        help="顶层为数组时, 将每个元素拆成独立的 JSON 输出")
    parser.add_argument("-F", "--fields", default="",
                        help="仅输出指定字段, 多个用逗号分隔, 支持点号嵌套路径, "
                             "如 -F name,meta.id")
    parser.add_argument("--filter", default=None,
                        help="按条件过滤对象: 字段 运算符 值(如 name=\"test\" / age > 10)。"
                             "可多次使用(各条件为或关系); 单次内多个条件用 | 分隔(或关系), "
                             "如 --filter 'name=\"test\" | age > 10'")
    parser.add_argument("--debug", action="store_true", help="显示调试信息")
    args = parser.parse_args()
    Config.debug = args.debug
    
    if args.filename:
        with open(args.filename, encoding="utf-8") as fp:
            text = fp.read()
    else:
        text = sys.stdin.read()

    fields = [f.strip() for f in args.fields.split(",") if f.strip()] \
        if args.fields else []

    ctx = JsonFormatter(compact=args.compact, sort_keys=args.sort_keys,
                        keep_text=args.keep_text, flat=args.flat,
                        split=args.split, fields=fields)
    try:
        # 先解析 --filter 参数, 构造过滤结构(仅一次, 不在循环里解析)
        filter_obj = build_filter(args.filter)
        if Config.debug:
            print(f"DEBUG: filter_obj={filter_obj}")
        ctx.format_text(text, filter_obj=filter_obj)
    except ValueError as e:
        sys.stderr.write("duck-json: %s\n" % e)
        sys.exit(1)


if __name__ == "__main__":
    format_json()
