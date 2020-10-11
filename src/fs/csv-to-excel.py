#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/02/24 01:58:21
# @modified 2020/10/11 12:42:01

import csv
import xlwt
import xlrd
import os
import sys
import argparse
from collections import namedtuple

csv.field_size_limit(500 * 1024 * 1024)

try:
    import xlwt
    import xlrd
except ImportError:
    xlwt = None
    xlrd = None

def write_row(worksheet, lineno, row):
    for n, item in enumerate(row):
        worksheet.write(lineno, n, item)
        
def write_excel_data(filepath, data):
    workbook = xlwt.Workbook(encoding = 'utf-8')
    worksheet = workbook.add_sheet('Worksheet')
    for lineno, row in enumerate(data):
        write_row(worksheet, lineno, row)
    workbook.save(filepath)
    
        
def read_excel_data(filepath, sheet_name):
    workbook = xlrd.open_workbook(filepath)
    # sheet_names = workbook.sheet_names()
    sheet = workbook.sheet_by_name(sheet_name)
    for row in sheet.get_rows():
        print(row)

def read_csv_data(filepath):
    with open(filepath) as f:
        reader = csv.reader(f)
        data = list(reader)
        for row in data[:10]:
            print(row)
        print('......')
        return data

def main(path=None, confirmed = False, **kw):
    data = read_csv_data(path)
    newpath, _ = os.path.splitext(path)
    newpath += '.xls'
    if not confirmed:
        print('将会转换成', newpath)
    else:
        write_excel_data(newpath, data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("fpath")
    args = parser.parse_args()
    main(args.fpath, True)


