# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2024-04-30 01:22:13
LastEditors: xupingmao
LastEditTime: 2024-05-01 18:50:56
FilePath: /duck_rush/duck_rush/fs/file-sha1.py
Description: 描述
'''
#!/usr/bin/env python 2
#coding : utf-8 3 
import hashlib
import os
import fire

CHUNK_SIZE = 8096

def sha1_sum(fname=""):
    """ 计算文件的SHA1值
    """
    def read_chunks(fh):
        fh.seek(0)
        chunk = fh.read(CHUNK_SIZE)
        while chunk:
            yield chunk
            chunk = fh.read(CHUNK_SIZE)
        else: #最后要将游标放回文件开头
            fh.seek(0)
    
    m = hashlib.sha1()
    with open(fname, "rb") as fh:
        for chunk in read_chunks(fh):
            m.update(chunk)
    return m.hexdigest()

def main(path=None, **kw):
    if os.path.isdir(path):
        for name in os.listdir(path):
            child_path = os.path.join(path, name)
            if os.path.isfile(child_path):
                print('%s  %s' % (sha1_sum(child_path), child_path))
    else:
        print('SHA1 =', sha1_sum(path))


if __name__ == "__main__":
    fire.Fire(main)
