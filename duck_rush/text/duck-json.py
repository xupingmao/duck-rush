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
from collections import OrderedDict
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
    "eq": operator.eq,
    "!=": operator.ne,
    "ne": operator.ne,
    ">=": operator.ge,
    "ge": operator.ge,
    "<=": operator.le,
    "le": operator.le,
    ">": operator.gt,
    "gt": operator.gt,
    "<": operator.lt,
    "lt": operator.lt,
}


# 运算符按长度从长到短排列, 避免把 >= 误判为 = 或 >
_OP_SEQ = ["!=", ">=", "<=", "=="]

# 再加入其他操作符
for _op in _OP_MAP:
    if _op not in _OP_SEQ:
        _OP_SEQ.append(_op)


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

    def __init__(self, terms: List[FilterTerm]):
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
                # 字母型操作符(ge/gt/le/lt/eq/ne)不能匹配字段名内部的子串,
                # 如 "age" 中的 "ge"; 需前后都不是字母才算边界匹配
                if op.isalpha():
                    prev = term[i - 1] if i > 0 else ""
                    nxt = term[i + len(op)] if i + len(op) < len(term) else ""
                    if (prev and prev.isalpha()) or (nxt and nxt.isalpha()):
                        continue
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


def match_filter(obj, filter_obj: Optional[FilterExpr] = None) -> bool:
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


class JsonRenderer:
    """格式化/序列化上下文: 负责把单条 JSON 记录渲染为字符串(支持拍平/
    fields 筛选), 以及把分组统计结果渲染为对齐表格。

    - compact  : 一行展示一个 JSON(否则美化, 每个 JSON 之间空一行)
    - sort_keys: 按 key 排序输出
    - keep_text: 保留并原样输出 JSON 之间的非 JSON 文本
    - flat    : 将嵌套 JSON 拍平为用 ``sep`` 连接的单层 dict 再输出
    - sep     : 拍平时连接 key 的分隔符, 默认 ``.``
    - fields  : 仅输出指定的字段(支持用 ``sep`` 连接的嵌套路径, 多个用逗号分隔)
    """

    def __init__(self, compact: bool = False, sort_keys: bool = False,
                 keep_text: bool = False, flat: bool = False, sep: str = ".",
                 fields: Optional[list] = None):
        self.compact = compact
        self.sort_keys = sort_keys
        self.keep_text = keep_text
        self.flat = flat
        self.sep = sep
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

    def pick(self, obj: object, wanted: Optional[dict] = None) -> object:
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

    def flatten(self, obj: object, prefix: str = "", result: Optional[dict] = None):
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

    @staticmethod
    def _fmt_num(v) -> str:
        """数值格式化为字符串: 整数去小数点, 浮点数最多保留 4 位小数。"""
        if isinstance(v, float):
            if v.is_integer():
                return str(int(v))
            return ("%.4f" % v).rstrip("0").rstrip(".")
        return str(v)

    # 分组/过滤/排序逻辑已重构为 Volcano 算子(见文件下方)

    def _print_group_table(self, result: list, group_fields: List[str], fields: list):
        """把分组统计结果打印为对齐的纯文本表格。"""
        headers = list(group_fields) + ["count"]
        for field in fields:
            headers += ["%s.avg" % field, "%s.max" % field, "%s.min" % field]

        rows = []
        for group in result:
            gval = group["group"]
            gvals = [gval] if isinstance(gval, str) else \
                [gval.get(f, "") for f in group_fields]
            row = [str(v) for v in gvals] + [str(group["count"])]
            stats = group.get("stats", {})
            for field in fields:
                s = stats.get(field)
                if s:
                    row += [self._fmt_num(s["avg"]),
                            self._fmt_num(s["max"]),
                            self._fmt_num(s["min"])]
                else:
                    row += ["-", "-", "-"]
            rows.append(row)

        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))

        def render(cells):
            out = []
            for i, cell in enumerate(cells):
                if i < len(group_fields):
                    out.append(cell.ljust(widths[i]))
                else:
                    out.append(cell.rjust(widths[i]))
            return " ".join(out)

        print(render(headers))
        for row in rows:
            print(render(row))


# ===========================================================================
# Volcano 执行模型
# 每个算子实现 __iter__, 通过迭代从上游算子逐行拉取数据:
#   - ScanOp    : 步骤1, 解析输入, 每次 yield ('json', obj) 或 ('text', str)
#   - FilterOp  : 应用 --filter 条件
#   - GroupByOp : 阻塞式聚合, 按字段分组并统计
#   - SortOp    : 阻塞式, 对上游结果排序(在 group-by 之后执行)
# 步骤3(组装输出)在 format_json 中根据模式选择对应的输出函数。
# ===========================================================================


class Operator:
    """Volcano 算子基类: 每个算子通过``source``持有唯一的上游迭代器,
    线性串联成流水线(非多子节点, 故用单数 source 而非 children)。"""
    def __init__(self, source: Optional['Operator'] = None):
        self.source = source

    def __iter__(self):
        raise NotImplementedError


class ScanOp(Operator):
    """步骤1: 从文本解析出片段, 每次 yield 一个 ('json', obj) 或 ('text', str)。"""
    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def __iter__(self):
        for kind, value in extract_segments(self.text):
            yield (kind, value)


class FilterOp(Operator):
    """应用 --filter 条件。顶层数组默认整体作为一个 json 行(可用 SplitOp 展开)。"""
    def __init__(self, source: Operator, filter_obj: Optional[FilterExpr] = None):
        super().__init__(source)
        self.filter_obj = filter_obj

    def __iter__(self):
        for kind, value in self.source:
            if kind != "json":
                yield (kind, value)
                continue
            if isinstance(value, list):
                kept = [it for it in value
                        if self.filter_obj is None or match_filter(it, self.filter_obj)]
                if kept:
                    yield ("json", kept)
            else:
                if self.filter_obj is None or match_filter(value, self.filter_obj):
                    yield ("json", value)


class SplitOp(Operator):
    """将顶层数组展开为独立的 json 行(对应 --split 参数)。"""
    def __iter__(self):
        for kind, value in self.source:
            if kind == "json" and isinstance(value, list):
                for it in value:
                    yield ("json", it)
            else:
                yield (kind, value)


def _discover_numeric_fields(records: List[dict]) -> List[str]:
    """自动发现记录中所有顶层数值型字段。"""
    fields: List[str] = []
    seen = set()
    for rec in records:
        if not isinstance(rec, dict):
            continue
        for k, v in rec.items():
            if k in seen:
                continue
            if _coerce_numeric(v) is not None:
                seen.add(k)
                fields.append(k)
    return fields


class GroupByOp(Operator):
    """阻塞式聚合: 收集所有 json 记录(顶层数组展开), 按字段分组并统计。"""
    def __init__(self, source: Operator, group_by: List[str],
                 stat_fields: Optional[list] = None, count_only: bool = False):
        super().__init__(source)
        self.group_by = group_by
        self.stat_fields = stat_fields
        self.count_only = count_only
        self.fields: List[str] = []  # 实际参与统计的字段(供输出制表用)

    def __iter__(self):
        # 收集所有 json 记录(dict), 顶层数组展开为多个记录
        records: List[dict] = []
        for kind, value in self.source:
            if kind != "json":
                continue
            items = value if isinstance(value, list) else [value]
            for it in items:
                if isinstance(it, dict):
                    records.append(it)

        self.fields = [] if self.count_only else (
            self.stat_fields or _discover_numeric_fields(records))

        groups = OrderedDict()
        for rec in records:
            key = tuple(_get_field(rec, f) for f in self.group_by)
            if any(v is None for v in key):
                continue
            groups.setdefault(key, []).append(rec)

        single = len(self.group_by) == 1
        for key, recs in groups.items():
            gval = key[0] if single else {f: v for f, v in zip(self.group_by, key)}
            row: dict = {"group": gval, "count": len(recs)}
            if not self.count_only:
                stats: dict = {}
                for field in self.fields:
                    vals = []
                    for rec in recs:
                        n = _coerce_numeric(_get_field(rec, field))
                        if n is not None:
                            vals.append(n)
                    if vals:
                        stats[field] = {
                            "avg": sum(vals) / len(vals),
                            "max": max(vals),
                            "min": min(vals),
                        }
                if stats:
                    row["stats"] = stats
            yield row


class SortOp(Operator):
    """阻塞式: 收集上游所有行, 按 key_fn 排序后输出。"""
    def __init__(self, source: Operator, key_fn, reverse: bool = False):
        super().__init__(source)
        self.key_fn = key_fn
        self.reverse = reverse

    def __iter__(self):
        rows = list(self.source)
        rows.sort(key=self.key_fn, reverse=self.reverse)
        for row in rows:
            yield row


class JsonOnlyOp(Operator):
    """过滤掉 text 行, 仅保留 json 行(排序等场景使用)。"""
    def __iter__(self):
        for kind, value in self.source:
            if kind == "json":
                yield (kind, value)


# ---- 排序键构造 -------------------------------------------------------------


def _make_group_key_fn(sort_keys: List[str], group_by: List[str]):
    """为分组结果行构造排序键函数。

    支持的键:
    - ``count``                 : 按分组记录数排序
    - 分组字段名               : 按该分组值排序(单字段分组时即 group 标量)
    - ``字段.avg/max/min``    : 按某数值属性的统计量排序
    """
    def fn(row):
        vals = []
        g = row.get("group")
        for key in sort_keys:
            if key == "count":
                vals.append(row.get("count", 0))
            elif "." in key:
                field, agg = key.split(".", 1)
                vals.append(row.get("stats", {}).get(field, {}).get(agg, 0))
            elif isinstance(g, dict):
                vals.append(g.get(key, ""))
            elif len(group_by) == 1 and key == group_by[0]:
                vals.append(g)
            else:
                vals.append("")
        return tuple(vals)
    return fn


def _make_record_key_fn(sort_keys: List[str]):
    """为普通 json 记录行 (kind, obj) 构造排序键函数。"""
    def fn(row):
        _, obj = row
        vals = []
        for key in sort_keys:
            v = _get_field(obj, key) if isinstance(obj, dict) else None
            n = _coerce_numeric(v)
            vals.append(n if n is not None else (v if v is not None else ""))
        return tuple(vals)
    return fn


# ---- 步骤3: 结果组装输出 ---------------------------------------------------


def output_group(op: Operator, meta_op: GroupByOp, as_json: bool, sort_keys: bool,
                 ctx: JsonRenderer):
    """输出分组统计结果(表格或 JSONL)。meta_op 提供 group_by/fields 元信息。"""
    rows = list(op)
    if not rows:
        if not as_json:
            print("无数据")
        return
    if as_json:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, sort_keys=sort_keys))
    else:
        ctx._print_group_table(rows, meta_op.group_by, meta_op.fields)


def output_plain(rows, ctx: JsonRenderer):
    """输出普通(json/text)结果: 应用 fields/flat, 按 keep_text 交织文本。"""
    items = []
    for kind, value in rows:
        if kind == "json":
            items.append(("json", ctx.dumps(value)))
        else:
            items.append(("text", value))
    if ctx.keep_text:
        print("".join(s for _, s in items))
    else:
        blocks = [s for k, s in items if k == "json"]
        joiner = "\n" if ctx.compact else "\n\n"
        if blocks:
            print(joiner.join(blocks))


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
    parser.add_argument("-f", "--flat", nargs="?", const=".", default=False,
                        metavar="SEP",
                        help="将嵌套 JSON 拍平为单层 dict 再输出; 可指定连接符, "
                             "如 -f _ 用下划线连接, 省略则默认用点号(.)连接")
    parser.add_argument("-S", "--split", action="store_true",
                        help="顶层为数组时, 将每个元素拆成独立的 JSON 输出")
    parser.add_argument("-F", "--fields", default="",
                        help="仅输出指定字段, 多个用逗号分隔, 支持点号嵌套路径, "
                             "如 -F name,meta.id")
    parser.add_argument("--filter", default=None,
                        help="按条件过滤对象: 字段 运算符 值(如 name=\"test\" / age > 10)。"
                             "可多次使用(各条件为或关系); 单次内多个条件用 | 分隔(或关系), "
                             "如 --filter 'name=\"test\" | age > 10'")
    parser.add_argument("--group-by", default="",
                        help="按指定顶层属性分组, 多个用逗号分隔(组合分组), "
                             "如 --group-by category,region。"
                             "配合 --stats 对各数值属性统计 count/avg/max/min")
    parser.add_argument("--stats", default="",
                        help="分组时统计的顶层数值属性, 多个用逗号分隔, "
                             "如 --stats price,score; 省略则对所有顶层数值属性统计")
    parser.add_argument("--table", action="store_true",
                        help="分组统计结果以对齐表格输出(默认输出为 JSONL)")
    parser.add_argument("--count", action="store_true",
                        help="分组时只统计 count, 不计算 avg/max/min")
    parser.add_argument("--sort-by", default="",
                        help="排序键, 多个用逗号分隔; 在 group-by 之后执行。"
                             "分组模式下可用: count / 分组字段名 / 字段.avg|max|min"
                             "(如 --sort-by count,price.avg); "
                             "普通模式下为顶层字段名(如 --sort-by age)。"
                             "配合 -r/--reverse 倒序")
    parser.add_argument("-r", "--reverse", action="store_true",
                        help="排序结果倒序(从大到小)")
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

    flat = args.flat is not False
    sep = args.flat if flat else "."
    ctx = JsonRenderer(compact=args.compact, sort_keys=args.sort_keys,
                        keep_text=args.keep_text, flat=flat, sep=sep,
                        fields=fields)
    try:
        # 先解析 --filter 参数, 构造过滤结构(仅一次, 不在循环里解析)
        filter_obj = build_filter(args.filter)
        if Config.debug:
            print(f"DEBUG: filter_obj={filter_obj}")

        # 步骤1: 解析输入为片段迭代器
        scan = ScanOp(text)

        sort_keys = [s.strip() for s in args.sort_by.split(",") if s.strip()] \
            if args.sort_by else None

        if args.group_by:
            group_by = [f.strip() for f in args.group_by.split(",") if f.strip()]
            stat_fields = [f.strip() for f in args.stats.split(",") if f.strip()] \
                if args.stats else None
            # 组装算子链: scan -> filter -> group-by
            op = FilterOp(scan, filter_obj)
            group_op = GroupByOp(op, group_by, stat_fields, args.count)
            final = group_op
            if sort_keys:
                # 排序在 group-by 之后执行
                final = SortOp(final,
                               _make_group_key_fn(sort_keys, group_by),
                               args.reverse)
            # 步骤3: 组装输出(表格 / JSONL)
            output_group(final, group_op, as_json=not args.table,
                        sort_keys=args.sort_keys, ctx=ctx)
        else:
            if sort_keys:
                # 排序时把顶层数组展开为独立记录, 并丢弃文本行
                op = SplitOp(scan)
                op = FilterOp(op, filter_obj)
                op = JsonOnlyOp(op)
                op = SortOp(op, _make_record_key_fn(sort_keys), args.reverse)
            else:
                op = FilterOp(scan, filter_obj)
                if args.split:
                    op = SplitOp(scan)
                    op = FilterOp(op, filter_obj)
            # 步骤3: 组装输出(美化 / 紧凑 / 保留文本)
            output_plain(list(op), ctx)
    except ValueError as e:
        sys.stderr.write("duck-json: %s\n" % e)
        sys.exit(1)


if __name__ == "__main__":
    format_json()
