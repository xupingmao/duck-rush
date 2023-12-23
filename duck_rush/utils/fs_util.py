# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/11/21 11:35:22
# @modified 2020/11/21 11:46:43
import os
import time
import sys
import shutil

IS_PY2 = sys.version_info[0] == 2

class FsException(Exception):
    pass

def get_file_size(fpath):
    if not os.path.exists(fpath):
        raise FsException("file not exists: %s" % fpath)
    try:
        st = os.stat(fpath)
        if st:
            return st.st_size
        else:
            raise FsException("stat file failed: " + fpath)
    except OSError as e:
        raise FsException("stat file failed: %s" % fpath)


def touch_file(path):
    """类似于Linux的touch命令"""
    if not os.path.exists(path):
        with open(path, "wb") as fp:
            pass
    else:
        current = time.mktime(time.gmtime())
        times = (current, current)
        os.utime(path, times)

def makedirs(dirname):
    '''检查并创建目录(如果不存在不报错)'''
    if not os.path.exists(dirname):
        os.makedirs(dirname)
        return True
    return False

def _try_read_file(path, mode = "r", limit = -1, encoding = 'utf-8'):
    if IS_PY2:
        with open(path) as fp:
            if limit > 0:
                content = fp.read(limit)
            else:
                content = fp.read()
            return content.decode(encoding)
    else:
        with open(path, encoding=encoding) as fp:
            if limit > 0:
                content = fp.read(limit)
            else:
                content = fp.read()
            return content

def read_file(path, mode = "r", limit = -1, raise_error = True):
    '''读取文件，尝试多种编码，编码别名参考标准库`Lib/encodings/aliases.py`
    * utf-8 是一种边长编码，兼容ASCII
    * GBK 是一种双字节编码，全称《汉字内码扩展规范》，兼容GB2312
    * latin_1 是iso-8859-1的别名，单字节编码，兼容ASCII
    '''
    last_err = None
    for encoding in ENCODING_TUPLE:
        try:
            return _try_read_file(path, mode, limit, encoding)
        except Exception as e:
            last_err = e
    if raise_error:
        raise Exception("readfile failed: %s" % path, last_err)

def write_file(path, content, mode = "wb"):
    import codecs
    dirname = os.path.dirname(path)
    makedirs(dirname)

    with open(path, mode=mode) as fp:
        if PY2 and isinstance(content, str):
            # Python2 环境下, str和byte完全一样，不需要编码成utf8
            buf = content
        elif is_str(content):
            buf = codecs.encode(content, "utf-8")
        else:
            buf = content
        fp.write(buf)
    return content


def rmtree(dirname=""):
    if os.path.exists(dirname):
        shutil.rmtree(dirname)