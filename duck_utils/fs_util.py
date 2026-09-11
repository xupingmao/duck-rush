# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/11/21 11:35:22
# @modified 2020/11/21 11:46:43
import os
import sys
import shutil
import base64
import logging
import subprocess
import time
from typing import Optional
from urllib.parse import unquote

from duck_utils import os_util

IS_PY2 = sys.version_info[0] == 2

# 编码文件名时使用的扩展名（命中这些扩展名则认为已经是编码后的文件名）
ENCODE_NAME_EXT = (".x0", ".xenc")

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
        
        

def get_relative_path(path="", parent=""):
    """获取文件相对parent的路径
    @param {str} path 当前文件路径
    @param {str} parent 父级文件路径
    @return {str} 相对路径
    
    >>> get_relative_path('/users/xxx/test/hello.html', '/users/xxx')
    'test/hello.html'
    >>> get_relative_path('/tmp/test.html', '/tmp/test.html')
    ''
    """
    path1 = os.path.abspath(path)
    parent1 = os.path.abspath(parent)
    # abpath之后最后没有/
    # 比如
    # ./                 -> /users/xxx
    # ./test/hello.html  -> /users/xxx/test/hello.html
    # 相减的结果是         -> /test/hello.html
    # 需要除去第一个/
    relative_path = path1[len(parent1):]
    relative_path = relative_path.replace("\\", "/")
    if relative_path.startswith("/"):
        relative_path = relative_path[1:]
    return relative_path


def encode_name(name: str) -> str:
    """对文件名进行 base64 编码, 以避免文件系统的编码问题

    编码后的文件名以 `.x0` 结尾, 命中 ENCODE_NAME_EXT 的文件名直接原样返回。
    """
    namepart, ext = os.path.splitext(name)
    if ext in ENCODE_NAME_EXT:
        return name
    result = base64.urlsafe_b64encode(name.encode("utf-8")).decode("utf-8")
    result = result.strip("=")
    return result + ".x0"


def decode_name(name: str) -> str:
    """将编码后的文件名解码成可读的名称

    先尝试按 base64(`.x0`/`.xenc` 扩展名)解码, 失败则按 urlencode 解码。
    """
    dirname = os.path.dirname(name)
    basename = os.path.basename(name)
    namepart, ext = os.path.splitext(basename)
    if ext in ENCODE_NAME_EXT:
        try:
            pad_size = 4 - len(namepart) % 4
            namepart += '=' * pad_size
            basename = base64.urlsafe_b64decode(
                namepart.encode("utf-8")).decode("utf-8")
            return os.path.join(dirname, basename)
        except Exception:
            pass
    return unquote(name)



def _get_linux_birth_time(fpath: str) -> Optional[float]:
    """Linux 上通过 `stat -c %W` 尽力获取创建时间 (birth time)

    文件系统或 stat 命令不支持时返回 None。
    """
    try:
        proc = subprocess.run(
            ["stat", "-c", "%W", fpath],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    text = proc.stdout.decode("utf-8", errors="ignore").strip()
    try:
        value = int(text)
    except ValueError:
        return None
    if value <= 0:
        return None
    return float(value)


def get_file_create_time(fpath: str) -> float:
    """跨平台获取文件创建时间戳 (秒, 浮点数)

    策略:
    * 优先 os.stat().st_birthtime (Windows Python>=3.12 / macOS / FreeBSD)
    * Windows 旧版本: st_ctime 表示创建时间
    * Linux: 标准库一般不暴露 birth time, 尝试 `stat -c %W` 命令,
      仍失败则回退修改时间 (mtime) 并打印提示
    """
    st = os.stat(fpath)
    birthtime = getattr(st, "st_birthtime", None)
    if birthtime is not None and birthtime > 0:
        return float(birthtime)
    if os_util.is_windows():
        # Windows 上 st_ctime 即创建时间 (st_birthtime 需 Python>=3.12)
        return float(st.st_ctime)
    if os_util.is_mac():
        # macOS 一般可拿到 st_birthtime; 兜底
        logging.warning("无法获取文件创建时间, 回退使用修改时间: %s", fpath)
        return float(st.st_mtime)
    # Linux
    birth = _get_linux_birth_time(fpath)
    if birth is not None:
        return birth
    logging.warning("当前平台无法获取文件创建时间, 回退使用修改时间: %s", fpath)
    return float(st.st_mtime)
