# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2023-12-23 13:16:20
LastEditors: xupingmao
LastEditTime: 2023-12-23 13:21:27
FilePath: /duck_rush/duck_rush/code/code-tools/format-json.py
Description: 描述
'''

import sys
import json
import fire

def format_json():
    """格式化json并且打印"""
    text = sys.stdin.read()
    obj = json.loads(text)
    print(json.dumps(obj, sort_keys=True, indent="  ", ensure_ascii=False))

if __name__ == "__main__":
    fire.Fire(format_json)
