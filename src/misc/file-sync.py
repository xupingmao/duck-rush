#!/usr/local/bin/python3
# encoding=utf-8
import os
import hashlib
import sys
import argparse

CHUNK_SIZE = 8096

def md5hex(word):
    """ MD5加密算法，返回32位小写16进制符号""" 
    if isinstance(word, unicode):
        word = word.encode("utf-8")
    elif not isinstance(word, str):
        word = str(word)
        m = hashlib.md5()
        m.update(word)
        return m.hexdigest()

def md5sum(fname):
    """ 计算文件的MD5值"""
    def read_chunks(fh):
        fh.seek(0)
        chunk = fh.read(CHUNK_SIZE)
        while chunk:
            yield chunk
            chunk = fh.read(CHUNK_SIZE)
        else: #最后要将游标放回文件开头
            fh.seek(0)

    if not os.path.exists(fname):
        return ""

    m = hashlib.md5()
    with open(fname, "rb") as fh:
        for chunk in read_chunks(fh):
            m.update(chunk)
    return m.hexdigest()

def calc_md5_sum():
    for root, dirs, files in os.walk("."):
        for fname in files:
            fpath = os.path.join(root, fname)
            # print("process %s ..." % fpath)
            md5_sum = md5sum(fpath)
            print("%s:%s" % (md5_sum, fname))

def check_md5_sum(path):
    md5_dict = {}
    with open(path) as fp:
        for line in fp.readlines():
            line = line.strip()
            if line == "":
                continue
            sep = line.find(":")
            if sep < 0:
                print("[error] invalid line: %s" % line)
            md5_sum = line[:sep]
            fname   = line[sep+1:]
            md5_dict[fname] = md5_sum

    path_list = []
    for root, dirs, files in os.walk("."):
        for fname in files:
            if fname in md5_dict:
                fpath = os.path.join(root, fname)
                path_list.append(fpath)

    dismatch_list = []
    for index, fpath in enumerate(path_list):
        fname = os.path.basename(fpath)
        # print(" " * 60 + '\r', end = '')
        print("[%d/%d] %s" % (index+1, len(path_list), fname))
        local_md5 = md5sum(fpath)
        remote_md5 = md5_dict[fname]
        if local_md5 != remote_md5:
            print("[dismatch] fname=%s, remote_md5=%s, local_md5=%s" % (fname, remote_md5, local_md5))
            dismatch_list.append(fname)

    print("\n\n")
    print("dismatch files".center(60, '-'))
    for fname in dismatch_list:
        print(fname)
def main():
    parser = argparse.ArgumentParser(description = "文件同步校验工具")
    parser.add_argument("action", help = "同步动作，可选的值有:check/sync/index")
    parser.add_argument("path", nargs = "?", help = "索引文件路径")
    args = parser.parse_args()

    if args.action == "index":
        calc_md5_sum()
    if args.action == "check":
        path = args.path
        if path is None:
            print("path is required")
            return
        check_md5_sum(path)

if __name__ == "__main__":
    main()