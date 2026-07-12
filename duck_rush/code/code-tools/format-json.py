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


def extract_json_fragments(text: str):
    """从文本中提取所有顶层 JSON(对象或数组)。

    找到每个 `{`/`[` 起始位置, 用 JSONDecoder.raw_decode 尝试解析:
    解析成功则记录结果并从其后的位置继续找下一个 JSON; 失败则跳过一个字符继续。

    输入可以是纯 JSON, 也可以是在前后夹杂其它文字的片段,
    例如日志行 `xxx {"a":1} yyy ["b"] end`。
    """
    decoder = json.JSONDecoder()
    results = []
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

        results.append(obj)
        i = end
    return results


def format_text(text: str, compact: bool, sort_keys: bool):
    """提取并格式化输出 JSON。

    - compact=False: 美化展示,每个 JSON 之间空一行
    - compact=True: 一行展示一个 JSON
    """
    objs = extract_json_fragments(text)
    if not objs:
        raise ValueError("未从输入中解析出任何 JSON")

    blocks = []
    for obj in objs:
        if compact:
            blocks.append(json.dumps(obj, ensure_ascii=False, sort_keys=sort_keys))
        else:
            blocks.append(json.dumps(
                obj, ensure_ascii=False, sort_keys=sort_keys, indent="  "))

    if compact:
        print("\n".join(blocks))
    else:
        print("\n\n".join(blocks))


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
    args = parser.parse_args()

    if args.filename:
        with open(args.filename, encoding="utf-8") as fp:
            text = fp.read()
    else:
        text = sys.stdin.read()

    format_text(text, compact=args.compact, sort_keys=args.sort_keys)


if __name__ == "__main__":
    format_json()
