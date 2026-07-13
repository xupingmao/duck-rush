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
    """

    def __init__(self, compact: bool = False, sort_keys: bool = False,
                 keep_text: bool = False, flat: bool = False, sep: str = ".",
                 split: bool = False):
        self.compact = compact
        self.sort_keys = sort_keys
        self.keep_text = keep_text
        self.flat = flat
        self.sep = sep
        self.split = split

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
        if self.flat:
            value = self.flatten(value)
        indent = None if self.compact else "  "
        return json.dumps(value, ensure_ascii=False, sort_keys=self.sort_keys,
                          indent=indent)

    def format_text(self, text: str):
        """提取并格式化输出 JSON。"""
        segments = extract_segments(text)
        if not segments:
            raise ValueError("未从输入中解析出任何 JSON")

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
    args = parser.parse_args()

    if args.filename:
        with open(args.filename, encoding="utf-8") as fp:
            text = fp.read()
    else:
        text = sys.stdin.read()

    ctx = JsonFormatter(compact=args.compact, sort_keys=args.sort_keys,
                        keep_text=args.keep_text, flat=args.flat,
                        split=args.split)
    ctx.format_text(text)


if __name__ == "__main__":
    format_json()
