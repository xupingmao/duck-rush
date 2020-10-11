#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/10/11 13:15:08
# @modified 2020/10/11 13:18:19

import argparse
from bs4 import BeautifulSoup


def fix_html_tags(fpath):
    html = open(fpath, encoding = "utf-8").read()
    soup = BeautifulSoup(html, "html.parser")
    print(soup.prettify())

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("fpath")
    args = parser.parse_args()
    fix_html_tags(args.fpath)
