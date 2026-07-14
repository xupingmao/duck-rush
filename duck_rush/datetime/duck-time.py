# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2024-09-02 00:06:21
LastEditors: xupingmao
LastEditTime: 2024-09-02 00:16:04
FilePath: /duck_rush/duck_rush/datetime/duck-time.py
Description: 时间转换工具
    - 时间戳(秒/毫秒) -> 日期字符串
    - 日期字符串      -> 时间戳
    - 相对时间(+10m/-10m/now) -> 时间戳
    输入同时支持参数和管道(stdin)
'''

import time
import sys
import re
import argparse

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 支持解析的日期格式（转时间戳时依次尝试）
DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S.%f",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M",
]

# 相对时间的单位换算（秒）
UNIT_SECONDS = {
    's': 1,
    'm': 60,
    'h': 3600,
    'd': 86400,
    'w': 604800,
    'y': 31536000,
}

# 相对时间语法: [+|-]数字 + 单位(可选, 默认 s) 例如 +10m -1h 30s 2d
RELATIVE_RE = re.compile(r'^([+-]?\d+(?:\.\d+)?)([smhdwy])$')

_YEAR = 3600 * 24 * 365
_MS_THRESHOLD = time.time() + _YEAR * 100  # 毫秒时间戳的阈值，比这个大自动判定成毫秒


class OutputConfig:
    debug = False
    ms = False        # 输出毫秒时间戳
    datetime = False  # 输出日期时间字符串


def format_time(unixtime: float = 0, format: str = DATE_FORMAT) -> str:
    st = time.localtime(unixtime)
    return time.strftime(format, st)


def parse_date_to_timestamp(date_str: str) -> float:
    for fmt in DATE_FORMATS:
        try:
            st = time.strptime(date_str, fmt)
            return time.mktime(st)
        except ValueError:
            continue
    raise ValueError("无法解析日期字符串: %s" % date_str)


def parse_relative(token: str) -> float:
    '''解析相对时间，例如 +10m 表示10分钟后，-1h 表示1小时前'''
    m = RELATIVE_RE.match(token)
    if not m:
        raise ValueError("无法解析相对时间: %s" % token)
    num = float(m.group(1))
    unit = m.group(2)
    return time.time() + num * UNIT_SECONDS[unit]


def to_timestamp(token: str) -> float:
    token = token.strip()
    if token == "" or token.lower() == "now":
        return time.time()
    # 相对时间（+10m / -10m / 30s / 2d）
    if RELATIVE_RE.match(token):
        return parse_relative(token)
    # 数字时间戳（秒 / 毫秒）
    try:
        return float(token)
    except ValueError:
        pass
    # 日期字符串
    return parse_date_to_timestamp(token)


def is_numeric(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False


def resolve(token: str):
    '''把输入解析为 (秒级时间戳, 是否毫秒输入, 原始毫秒值)'''
    if is_numeric(token):
        sec = float(token)
        if sec >= _MS_THRESHOLD:
            return sec / 1000.0, True, sec
        return sec, False, sec
    return to_timestamp(token), False, None


def process(token: str) -> None:
    token = token.strip()
    if token == "":
        return
    try:
        ts, is_ms, raw = resolve(token)
        if OutputConfig.datetime:
            # 日期时间字符串
            print(format_time(ts))
        elif OutputConfig.ms:
            # 毫秒时间戳（整数）
            ms = int(raw) if is_ms else int(ts * 1000)
            print(ms)
        else:
            # 默认：数字时间戳 -> 日期字符串；其余 -> 整数秒级时间戳
            if is_numeric(token):
                print(format_time(ts))
            else:
                print(int(ts))
        if OutputConfig.debug:
            sys.stderr.write("debug: ts=%d ms=%d date=%s\n"
                             % (int(ts), int(ts * 1000), format_time(ts)))
    except ValueError as e:
        sys.stderr.write("错误: %s\n" % e)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="时间转换工具: 时间戳<->日期, 支持相对时间")
    parser.add_argument("unixtime", nargs="*", default=[],
                        help="时间戳 / 日期字符串 / 相对时间(+10m/-1h/now), 多个以空格分隔")
    parser.add_argument("--ms", action="store_true", help="输出毫秒时间戳")
    parser.add_argument("--datetime", action="store_true", help="输出日期时间字符串")
    parser.add_argument("--debug", action="store_true", help="显示调试信息")
    args = parser.parse_args()

    OutputConfig.ms = args.ms
    OutputConfig.datetime = args.datetime
    OutputConfig.debug = args.debug

    if args.unixtime:
        for t in args.unixtime:
            process(t)
    else:
        for line in sys.stdin.readlines():
            line = line.strip()
            if line == "":
                continue
            process(line)
