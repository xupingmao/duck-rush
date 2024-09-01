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
import fire

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def format_time(unixtime=0, format=DATE_FORMAT):
    st = time.localtime(unixtime)
    return time.strftime(format, st)

def parse_date_to_timestamp(date_str=""):
    st = time.strptime(date_str, DATE_FORMAT)
    return time.mktime(st)

def main(unixtime="0"):
    sec = float(unixtime)

    if sec >= parse_date_to_timestamp("3000-01-01 00:00:00"):
        print(f"毫秒时间: {format_time(sec/1000)}")
    else:
        print(f"秒时间: {format_time(sec)}")

if __name__ == "__main__":
    fire.Fire(main)

