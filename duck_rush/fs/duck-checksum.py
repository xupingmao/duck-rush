# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2024-04-30 01:22:13
LastEditors: xupingmao
LastEditTime: 2024-08-17 17:25:48
FilePath: /duck_rush/duck_rush/fs/duck-checksum.py
Description: 描述
'''
#!/usr/bin/env python 2
#coding : utf-8 3 
import hashlib
import os
import fire

CHUNK_SIZE = 8096

hash_dict = {
    "sha1": hashlib.sha1(),
    "md5": hashlib.md5(),
    "sha256": hashlib.sha256(),
}

def get_hash_lib(hash_type=""):
    hash_type = hash_type.lower()
    m = hash_dict.get(hash_type)
    if m is None:
        raise Exception(f"unknown hash_type {hash_type}")
    return m

def calc_checksum(fname="", checksum_type="sha1"):
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
    
    m = get_hash_lib(checksum_type)
    with open(fname, "rb") as fh:
        for chunk in read_chunks(fh):
            m.update(chunk)
    return m.hexdigest()

def main(path:str, checksum_type="sha1", **kw):
    if os.path.isdir(path):
        for name in os.listdir(path):
            child_path = os.path.join(path, name)
            if os.path.isfile(child_path):
                print('%s  %s' % (calc_checksum(child_path, checksum_type=checksum_type), child_path))
    else:
        print(f'{checksum_type}:', calc_checksum(path, checksum_type=checksum_type))


if __name__ == "__main__":
    fire.Fire(main)
