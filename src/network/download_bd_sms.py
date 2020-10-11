
import time
import os
import json

TPL = ""

# 保存百度短信的cURL代码到bd_curl_sms.txt文件中
with open("bd_curl_sms.txt") as fp:
    TPL = fp.read()

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
        # print(command)
        os.system(command)
        start += limit

        data = json.load(open(filename))
        # print(data)
        print("start:%06d, size:%d" % (start, len(data.get("list"))))

        if len(data.get("list")) == 0:
            break

download()


