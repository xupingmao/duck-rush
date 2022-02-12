# encoding=utf-8
import os
import hashlib
import argparse
import sys
import re

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

    m = hashlib.md5()
    if isinstance(fname, str) and os.path.exists(fname):
        with open(fname, "rb") as fh:
            for chunk in read_chunks(fh):
                m.update(chunk)
    #上传的文件缓存 或 已打开的文件流
    elif fname.__class__.__name__ in ["StringIO", "StringO"] or isinstance(fname, file):
        for chunk in read_chunks(fname):
            m.update(chunk)
    else:
        return ""
    return m.hexdigest()

def calc_md5_sample(fpath):
    m = hashlib.md5()

    with open(fpath, "rb") as fp:
        while True:
            chunk = fp.read(CHUNK_SIZE)
            if not chunk:
                break
            m.update(chunk)
            fp.seek(fp.tell() + CHUNK_SIZE * 9)
    return m.hexdigest()


def is_matched(source, search_key):
    return search_key != "" and search_key in source

def is_not_match(source, search_key):
    return not is_matched(source, search_key)

def format_size(size):
    """格式化大小

    >>> format_size(10240)
    '10.00K'
    >>> format_size(1429365116108)
    '1.3T'
    >>> format_size(1429365116108000)
    '1.3P'
    """
    if size < 1024:
        return '%sB' % size
    elif size < 1024 **2:
        return '%.2fK' % (float(size) / 1024)
    elif size < 1024 ** 3:
        return '%.2fM' % (float(size) / 1024 ** 2)
    elif size < 1024 ** 4:
        return '%.2fG' % (float(size) / 1024 ** 3)
    elif size < 1024 ** 5:
        return '%.2fT' % (float(size) / 1024 ** 4)
    else:
        return "%.2fP" % (float(size) / 1024 ** 5)

def get_file_size(fpath, format = True):
    try:
        stat = os.stat(fpath)
        if format == True:
            return format_size(stat.st_size)
        else:
            return stat.st_size
    except:
        return "Error"

def check_arg_move_to(move_to):
    if move_to == "":
        return

    if not os.path.exists(move_to):
        print("参数错误: 文件不存在: %s" % move_to)
        sys.exit(1)
    if not os.path.isdir(move_to):
        print("参数错误: 文件夹不存在: %s" % move_to)
        sys.exit(1)


def parse_file_size(min_size_str, arg_name, exit_on_error = True):
    if min_size_str == "":
        return -1

    min_size_str = min_size_str.lower()

    p_k = re.compile(r"(\d+)k$")
    if p_k.match(min_size_str):
        m = p_k.match(min_size_str)
        return int(m.group(1)) * 1024

    p_m = re.compile(r"(\d+)m$")
    if p_m.match(min_size_str):
        m = p_m.match(min_size_str)
        return int(m.group(1)) * 1024 * 1024

    p_g = re.compile(r"(\d+)g$")
    if p_g.match(min_size_str):
        m = p_g.match(min_size_str)
        return int(m.group(1)) * 1024 ** 3

    if exit_on_error:
        print("参数错误： (%s)无效的文件大小: %s" % (arg_name, min_size_str))
        print("文件大小示例: 50 50k 50m 1g (不支持小数)")
        sys.exit(1)
    else:
        raise Exception("无效的文件大小: %s" % min_size_str)

class FileFinder:

    def __init__(self):
        self.hash_type = "none"
        self.search_names = []
        self.move_to = ""
        self.print_size = False
        self.print_base_name = False
        self.min_size = -1
        self.max_size = -1

    def set_min_size(self, min_size_str):
        self.min_size = parse_file_size(min_size_str, "min_size")

    def set_max_size(self, max_size_str):
        self.max_size = parse_file_size(max_size_str, "max_size")

    def set_move_to_dir(self, move_to):
        if move_to == "":
            self.move_to = ""
            return

        check_arg_move_to(move_to)
        self.move_to = os.path.abspath(move_to)

    def calc_hash_value(self, fpath):
        hash_type = self.hash_type

        if hash_type == "md5":
            hash_value = md5sum(fpath)
        elif hash_type == "md5_sample":
            hash_value = calc_md5_sample(fpath)
        else:
            hash_value = "none_hash"

        return hash_value

    def is_name_matched(self, fname):
        if len(self.search_names) == 0:
            return True

        for name in self.search_names:
            if name not in fname:
                return False

        return True

    def is_size_matched(self, size):
        if self.min_size > 0 and size < self.min_size:
            return False

        if self.max_size > 0 and size > self.max_size:
            return False

        return True

    def check_args(self):
        check_arg_move_to(self.move_to)

    def get_new_path(self, fpath, target):
        fname = os.path.basename(fpath)
        name, ext = os.path.splitext(fname)
        suffix = 0

        while True:
            if suffix == 0:
                fname = name + ext
            else:
                fname = "%s(%d)%s" % (name, suffix, ext)

            newpath = os.path.join(self.move_to, fname)

            if not os.path.exists(newpath):
                return newpath

            suffix += 1
            if suffix > 20:
                raise Exception("尝试太多次的重命名!!!(%s)" % fpath)


    def move_file(self, fpath):
        if self.move_to == "":
            return

        dirname = os.path.dirname(fpath)
        dirname = os.path.abspath(dirname)

        if dirname == self.move_to:
            print("-- 已经在目标文件夹内了")
            return
        else:
            newpath = self.get_new_path(fpath, self.move_to)
            print("")
            print("移动文件...")
            print("源文件: %s" % fpath)
            print("目的文件: %s" % newpath)
            print("")
            os.rename(fpath, newpath)


    def execute(self):
        self.check_args()
        hash_type = self.hash_type
        move_to = self.move_to
        print_base_name = self.print_base_name

        count = 0
        total_size = 0
        
        for root, dirs, files in os.walk("."):
            for fname in files:
                fpath = os.path.join(root, fname)
                # print("process %s ..." % fpath)

                if not self.is_name_matched(fname):
                    continue

                try:
                    stat = os.stat(fpath)
                except:
                    print("--- 读取文件状态失败, fname=%s" % fpath)
                    continue

                file_size = stat.st_size
                if not self.is_size_matched(file_size):
                    continue

                hash_value = self.calc_hash_value(fpath)

                count += 1

                if print_base_name:
                    path_to_print = fname
                else:
                    path_to_print = os.path.abspath(fpath)

                line_buf = []
                line_buf.append("%04d" % count)
                line_buf.append(hash_value)

                if not self.hide_size:
                    total_size += file_size
                    line_buf.append("%s" % format_size(file_size))

                line_buf.append(path_to_print)
                print("|".join(line_buf))

                self.move_file(fpath)

        if count == 0:
            print("\n没有找到文件\n")

        if count > 0 and not self.hide_size:
            print("\n文件总大小: %s" % format_size(total_size))


def main():
    parser = argparse.ArgumentParser()
    # action有很多选项
    # 'store': 默认值，存储选项
    # 'store_const': 存储常量，和`const`参数一起搭配使用
    #       >>> parser = argparse.ArgumentParser()
    #       >>> parser.add_argument('--foo', action='store_const', const=42)
    #       >>> parser.parse_args(['--foo'])
    #       Namespace(foo=42)
    # 'store_true' : 如果有这个选项就设置成True
    # 'store_false': 如果有这个选项就设置成False
    # 'append': 存储成一个列表，可以追加多个值
    # 'append_const': 

    parser.add_argument("--hash", default = "none", help = "文件hash算法")
    parser.add_argument("--name", default = [], action = "append", help = "搜索名称")
    parser.add_argument("--move_to", default = "", help = "移动到的目标文件夹")
    parser.add_argument("--hide_size", action = "store_true", help = "隐藏文件大小的信息")
    parser.add_argument("--print_base_name", action = "store_true", help = "只打印文件名，不打印全路径")
    parser.add_argument("--index_file", help = "保存的索引文件名称")
    parser.add_argument("--min_size", default = "", help = "文件大小下限")
    parser.add_argument("--max_size", default = "", help = "文件大小上限")
    args = parser.parse_args()

    finder = FileFinder()

    finder.hash_type = args.hash
    finder.search_names = args.name
    finder.set_move_to_dir(args.move_to)
    finder.hide_size = args.hide_size
    finder.print_base_name = args.print_base_name
    finder.set_min_size(args.min_size)
    finder.set_max_size(args.max_size)

    finder.execute()

if __name__ == "__main__":
    main()
