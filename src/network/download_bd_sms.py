'''
Author: xupingmao 578749341@qq.com
Date: 2019-12-14 18:30:11
LastEditors: xupingmao 578749341@qq.com
LastEditTime: 2023-12-17 17:46:12
FilePath: /901_duck_rush/src/network/download_bd_sms.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''

import time
import os
import json
import sys

TPL_EXAMPLE = """
curl 'https://duanxin.baidu.com/rest/2.0/pim/message?method=list&box=receive&app_id=20&imei=&card=&limit=0-99&t=1702805896289' \
  -H 'Accept: application/json, text/javascript, */*; q=0.01' \
  -H 'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8' \
  -H 'Connection: keep-alive' \
  -H 'Cookie: Example' \
  -H 'Referer: Example' \
  -H 'Sec-Fetch-Dest: empty' \
  -H 'Sec-Fetch-Mode: cors' \
  -H 'Sec-Fetch-Site: same-origin' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' \
  -H 'X-Requested-With: XMLHttpRequest' \
  -H 'sec-ch-ua: "Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "macOS"' \
  --compressed
"""
TPL = ""
CONFIG_FILE = "bd_curl_sms.txt"

def replace_between(self, start, end, target):
    p1 = self.find(start)
    if p1 < 0:
        return ""
    p2 = self.find(end, p1)
    if p2 < 0:
        return ""
    # return self[p1+len(start):p2]
    return self[:p1 + len(start)] + target + self[p2:]

def makedirs(dirname):
    '''检查并创建目录(如果不存在不报错)'''
    if not os.path.exists(dirname):
        os.makedirs(dirname)
        return True
    return False

def download():
    start = 0
    limit = 100

    dirname = "sms2"
    makedirs(dirname)

    while True:
        command = TPL
        command = replace_between(command, "limit=", "&", "%s-%s" % (start, start + limit - 1))
        command = replace_between(command, "&t=", "'", str(int(time.time() * 1000)))

        filename = dirname + "/sms_%s.json" % start
        command  = command + " > " + filename
        print(command)
        os.system(command)
        start += limit

        with open(filename, encoding="utf-8") as fp:
            data = json.load(fp)
            # print(data)
            print("start:%06d, size:%d" % (start, len(data.get("list"))))

            if len(data.get("list")) == 0:
                break


def print_edit_help():
    print("请先编辑 bd_curl_sms.txt 配置")
    with open(CONFIG_FILE, "w+", encoding="utf-8") as fp:
        fp.write(TPL_EXAMPLE)
    
    sys.exit(1)

def check_config():
    # 保存百度短信的cURL代码到bd_curl_sms.txt文件中
    global TPL
    
    if not os.path.exists(CONFIG_FILE):
        print_edit_help()

    with open("bd_curl_sms.txt", encoding="utf-8") as fp:
        TPL = fp.read()
    
    if TPL == "" or TPL == TPL_EXAMPLE:
        print_edit_help()

if __name__ == "__main__":
    check_config()
    download()

