# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2024-09-02 00:06:21
LastEditors: xupingmao
LastEditTime: 2024-09-02 00:16:04
FilePath: /duck_rush/duck_rush/datetime/format-time.py
Description: 描述
'''

import time
import sys
import argparse

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_YEAR = 3600 * 24 * 365
_MS_THRESHOLD = time.time() + _YEAR * 100 # 毫秒时间的阈值，如果比这个大自动判定成毫秒时间戳

class FormatConfig:
    debug = False

def format_time(unixtime:float=0, format=DATE_FORMAT):
    st = time.localtime(unixtime)
    return time.strftime(format, st)

def parse_date_to_timestamp(date_str=""):
    st = time.strptime(date_str, DATE_FORMAT)
    return time.mktime(st)

def main(unixtime="0"):
    if unixtime != "0":
        do_format(unixtime)
        return
        
    for line in sys.stdin.readlines():
        line = line.strip()
        if line == "":
            continue
        do_format(line)

def do_format(time_str: str):
    sec = float(time_str)
    if sec >= _MS_THRESHOLD:
        if FormatConfig.debug:
            print(f"毫秒时间: {format_time(sec/1000)}")
        else:
            print(format_time(sec/1000))
    else:
        if FormatConfig.debug:
            print(f"秒时间: {format_time(sec)}")
        else:
            print(format_time(sec))
            
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("unixtime", default="0", type=str, nargs="?")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    
    FormatConfig.debug = args.debug
    
    main(unixtime=args.unixtime)

