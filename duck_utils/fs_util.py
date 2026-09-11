# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/11/21 11:35:22
# @modified 2020/11/21 11:46:43
import os
import sys
import shutil
import base64
import logging
import re
import subprocess
import time
from datetime import datetime
from typing import NamedTuple, Optional
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


class DatePrefix(NamedTuple):
    """文件名开头的日期前缀

    text: 完整前缀, 含末尾分隔符 (如 `2026-09-11_`)
    date: 日期部分 (如 `2026-09-11`)
    sep : 日期与文件名之间的分隔符 (如 `_`)
    """
    text: str
    date: str
    sep: str


# 文件名开头常见的日期写法, 顺序与 DATE_PREFIX_RE 中的分支对应
DATE_TEXT_FORMATS = ("%Y-%m-%d", "%Y_%m_%d", "%Y.%m.%d", "%Y%m%d")

# 日期(可带时间部分) + 分隔符; 时间部分例如 `2026-09-11_123000_report`
DATE_PREFIX_RE = re.compile(
    r"""^(?P<date>
            \d{4}-\d{1,2}-\d{1,2}      # 2026-09-11
          | \d{4}_\d{1,2}_\d{1,2}      # 2026_09_11
          | \d{4}\.\d{1,2}\.\d{1,2}    # 2026.09.11
          | \d{8}                      # 20260911
        )
        (?:[-_ T]\d{6})?                # 可选的时间部分 HHMMSS
        (?P<sep>[-_ ])                 # 日期与文件名之间的分隔符
    """,
    re.VERBOSE)


def parse_date_text(text: str) -> Optional[datetime]:
    """把常见写法的日期文本解析成 datetime, 无法解析时返回 None

    同时排除 2026-13-45 这类越界值。
    """
    for fmt in DATE_TEXT_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _is_date_text(text: str) -> bool:
    return parse_date_text(text) is not None


def match_date_prefix(name: str) -> Optional[DatePrefix]:
    """识别文件名开头的常见日期前缀, 没有则返回 None

    支持 `20260911_` / `2026-09-11_` / `2026_09_11_` / `2026.09.11_` 等写法,
    日期后可带时间部分 (如 `2026-09-11_123000_`)。

    只对文件名主干(去掉目录与扩展名)做匹配, 因此 `20260911.txt` 这类
    "整个文件名就是日期"的情况不算日期前缀。

    >>> match_date_prefix("2026-09-11_report.pdf").date
    '2026-09-11'
    >>> match_date_prefix("report.pdf") is None
    True
    """
    stem = os.path.splitext(os.path.basename(name))[0]
    matched = DATE_PREFIX_RE.match(stem)
    if matched is None:
        return None
    date_text = matched.group("date")
    if not _is_date_text(date_text):
        return None
    return DatePrefix(text=matched.group(0), date=date_text,
                      sep=matched.group("sep"))


def has_date_prefix(name: str) -> bool:
    """文件名是否已带常见格式的日期前缀"""
    return match_date_prefix(name) is not None


def reformat_date_prefix(name: str, date_format: str, sep: str) -> str:
    """把文件名开头已有的日期前缀重新格式化成 date_format + sep

    * 只改写日期的写法, 日期之后的内容(时间部分与文件名本体)保持不变
    * 没有可识别的日期前缀时原样返回

    >>> reformat_date_prefix("2026-09-11_report.pdf", "%Y%m%d", "_")
    '20260911_report.pdf'
    >>> reformat_date_prefix("20260911_report.pdf", "%Y-%m-%d", "_")
    '2026-09-11_report.pdf'
    >>> reformat_date_prefix("report.pdf", "%Y%m%d", "_")
    'report.pdf'
    """
    prefix = match_date_prefix(name)
    if prefix is None:
        return name
    parsed = parse_date_text(prefix.date)
    if parsed is None:
        return name
    # 日期与时间部分之间的内容(如 `_123000`), 没有时间部分时为空串
    middle = prefix.text[len(prefix.date):len(prefix.text) - len(prefix.sep)]
    dirname, basename = os.path.split(name)
    new_basename = (parsed.strftime(date_format) + middle + sep
                    + basename[len(prefix.text):])
    return os.path.join(dirname, new_basename)


def strip_date_prefix(name: str) -> str:
    """删除文件名开头的常见日期前缀, 无前缀时原样返回

    >>> strip_date_prefix("2026-09-11_report.pdf")
    'report.pdf'
    """
    prefix = match_date_prefix(name)
    if prefix is None:
        return name
    # match_date_prefix 只匹配文件名主干, 切片前先剥掉目录部分
    dirname, basename = os.path.split(name)
    return os.path.join(dirname, basename[len(prefix.text):])
