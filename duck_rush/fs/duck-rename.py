# -*- coding: utf-8 -*-
"""文件名批量工具: base64 编解码 + 批量增删文件前缀/后缀/日期前缀

子命令:
* encode            - 对文件名进行 base64 编码
* decode            - 对编码文件名进行 base64 解码
* add-prefix        - 批量添加文件前缀
* remove-prefix     - 批量删除文件前缀
* add-suffix        - 批量添加文件后缀 (默认在扩展名之前)
* remove-suffix     - 批量删除文件后缀 (默认删除扩展名之前的后缀)
* add-date-prefix   - 按文件创建日期批量添加日期前缀 (如 20260908_xxx)
* remove-date-prefix - 批量删除文件日期前缀
* reformat-date-prefix - 把已有的日期前缀重新格式化 (如 2026-09-08_xxx => 20260908_xxx)

日期前缀说明:
* 日期默认取自文件创建时间, 格式默认 %Y%m%d (yyyyMMdd), 前缀形如 20260908_
* add-date-prefix 幂等: 已带常见日期前缀(20260908_ / 2026-09-08_ / 2026_09_08_ /
  2026.09.08_ 等)的文件会跳过, 不会重复叠加
* remove-date-prefix 除指定格式外, 也会兜底识别并删除上述常见格式的前缀
* reformat-date-prefix 只改写日期写法(如 2026-09-08_ => 20260908_), 不改动文件名本体,
  已是目标格式的文件保持不变 (幂等)
* Windows: st_birthtime (Python>=3.12) 或 st_ctime (旧版本即创建时间)
* macOS:   st_birthtime
* Linux:   标准库一般不暴露创建时间, 优先尝试 `stat -c %W` 命令,
           失败时回退使用文件修改时间 (mtime) 并给出提示

确认与输入说明:
* 除 encode/decode 外, 其他重命名命令都会先打印全部命名调整计划,
  交互确认后才批量执行 (-y/--yes 跳过确认, -n/--dry-run 只预览不执行)
* 支持从管道读取待处理文件列表: 加 -i/--stdin 后, 从标准输入按行读取文件路径
  代替扫描目录 (每行一个文件; 空行与 # 开头的注释行会被忽略)

用法示例:
* duck-rename add-prefix ./photos img_
* duck-rename add-suffix ./photos _v2 -n
* duck-rename remove-date-prefix ./photos -r -y
* duck-rename reformat-date-prefix ./photos -n  # 预览: 2026-09-08_xxx => 20260908_xxx
* duck-find . --name "*.jpg" | duck-rename add-prefix img_ -i -y
"""
import argparse
import logging
import os
import re
import sys
import time
from typing import Callable, List, Optional, Pattern, Tuple

try:
    from duck_utils import fs_util
except ImportError:
    sys.stderr.write("无法导入 duck_utils 模块, 请先执行 `python install.py` 安装后重试。\n")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s|%(levelname)s|%(message)s"
)

DEFAULT_MAX_DEPTH = 5

BATCH_COMMANDS = ("add-prefix", "remove-prefix", "add-suffix", "remove-suffix")
DATE_COMMANDS = ("add-date-prefix", "remove-date-prefix", "reformat-date-prefix")

DEFAULT_DATE_FORMAT = "%Y%m%d"
DEFAULT_DATE_SEP = "_"

# 管道输入的用法说明, 作为各重命名子命令 -h 的 epilog
PIPE_USAGE = """\
管道输入文件列表 (-i/--stdin, 每行一个路径, 空行与 # 开头的行忽略):
  duck-find . --name "*.jpg" | duck-rename add-prefix img_ -i -y
注意: 使用 -i 时忽略目录参数; 标准输入被管道占用无法交互确认,
      需加 -y/--yes 执行, 或用 -n/--dry-run 只预览。
"""

MAIN_EPILOG = """\
示例:
  duck-rename add-prefix ./photos img_            # 加前缀 img_
  duck-rename add-suffix ./photos _v2 -n          # 预览: 扩展名前加 _v2 (a.jpg -> a_v2.jpg)
  duck-rename remove-date-prefix ./photos -r -y   # 递归删除日期前缀, 不确认直接执行
  duck-rename encode ./data -d 2                  # base64 编码文件名, 最大递归 2 层

""" + PIPE_USAGE

# 支持的 strftime 令牌 -> 对应的正则片段
DATE_TOKEN_MAP = {
    "%Y": r"\d{4}", "%y": r"\d{2}",
    "%m": r"\d{2}", "%d": r"\d{2}",
    "%H": r"\d{2}", "%M": r"\d{2}", "%S": r"\d{2}",
    "%j": r"\d{3}",
}


def encode(dirname="./", max_depth=DEFAULT_MAX_DEPTH, current_depth=0):
    if current_depth > max_depth:
        logging.warning("到达最大递归深度 %s, 跳过目录: %s", max_depth, dirname)
        return
    for fname in os.listdir(dirname):
        new_name = fs_util.encode_name(fname)
        old_path = os.path.join(dirname, fname)
        new_path = os.path.join(dirname, new_name)
        is_dir = os.path.isdir(old_path)
        if is_dir and current_depth < max_depth:
            encode(old_path, max_depth, current_depth + 1)
        elif is_dir:
            logging.warning("到达最大递归深度 %s, 跳过目录: %s", max_depth, old_path)
        os.rename(old_path, new_path)


def decode(dirname="./", max_depth=DEFAULT_MAX_DEPTH, current_depth=0):
    if current_depth > max_depth:
        logging.warning("到达最大递归深度 %s, 跳过目录: %s", max_depth, dirname)
        return
    for fname in os.listdir(dirname):
        new_name = fs_util.decode_name(fname)
        old_path = os.path.join(dirname, fname)
        new_path = os.path.join(dirname, new_name)
        is_dir = os.path.isdir(old_path)
        if is_dir and current_depth < max_depth:
            decode(old_path, max_depth, current_depth + 1)
        elif is_dir:
            logging.warning("到达最大递归深度 %s, 跳过目录: %s", max_depth, old_path)
        os.rename(old_path, new_path)


def iter_files(dirname: str, recursive: bool) -> List[str]:
    """收集目录下需要处理的普通文件路径"""
    if not os.path.isdir(dirname):
        raise NotADirectoryError("目录不存在: %s" % dirname)
    files: List[str] = []
    if recursive:
        for dirpath, _, filenames in os.walk(dirname):
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                if os.path.isfile(fpath):
                    files.append(fpath)
    else:
        for name in os.listdir(dirname):
            fpath = os.path.join(dirname, name)
            if os.path.isfile(fpath):
                files.append(fpath)
    files.sort()
    return files


def add_prefix_name(name: str, prefix: str) -> str:
    """文件名开头添加前缀"""
    return prefix + name


def remove_prefix_name(name: str, prefix: str) -> str:
    """删除文件名开头的前缀, 无匹配时保持原名"""
    if prefix and name.startswith(prefix):
        return name[len(prefix):]
    return name


def add_suffix_name(name: str, suffix: str, after_ext: bool = False) -> str:
    """添加文件后缀; after_ext=True 时追加到扩展名之后"""
    if after_ext:
        return name + suffix
    namepart, ext = os.path.splitext(name)
    return namepart + suffix + ext


def remove_suffix_name(name: str, suffix: str, after_ext: bool = False) -> str:
    """删除文件后缀; after_ext=True 时从完整文件名末尾删除"""
    if suffix == "":
        return name
    if after_ext:
        if name.endswith(suffix):
            return name[:-len(suffix)]
        return name
    namepart, ext = os.path.splitext(name)
    if namepart.endswith(suffix):
        return namepart[:-len(suffix)] + ext
    return name


def build_date_prefix_pattern(date_format: str, sep: str) -> Pattern:
    """把 strftime 日期格式 + 分隔符转换成正则, 用于识别/删除日期前缀

    仅支持 DATE_TOKEN_MAP 中列出的数字型日期时间令牌, 其余字符按字面处理。
    """
    result = "^"
    index = 0
    while index < len(date_format):
        token = date_format[index:index + 2]
        if token in DATE_TOKEN_MAP:
            result += DATE_TOKEN_MAP[token]
            index += 2
            continue
        result += re.escape(date_format[index])
        index += 1
    result += re.escape(sep)
    return re.compile(result)


def add_date_prefix_name(name: str, date_str: str, sep: str) -> str:
    """在文件名开头添加日期前缀"""
    return date_str + sep + name


def strip_date_prefix_by_pattern(name: str, pattern: Pattern) -> str:
    """按给定格式删除文件名开头的日期前缀, 无匹配时保持原名"""
    return pattern.sub("", name, count=1)


def build_mapper(mode: str, text: str, after_ext: bool = False) -> Callable[[str], str]:
    """根据子命令构造 旧文件路径 -> 新文件名 的映射函数"""
    if mode == "add-prefix":
        return lambda path: add_prefix_name(os.path.basename(path), text)
    if mode == "remove-prefix":
        return lambda path: remove_prefix_name(os.path.basename(path), text)
    if mode == "add-suffix":
        return lambda path: add_suffix_name(os.path.basename(path), text, after_ext)
    if mode == "remove-suffix":
        return lambda path: remove_suffix_name(os.path.basename(path), text, after_ext)
    raise ValueError("未知的操作模式: %s" % mode)


def build_add_date_mapper(
    date_format: str = DEFAULT_DATE_FORMAT,
    sep: str = DEFAULT_DATE_SEP,
) -> Callable[[str], str]:
    """构造 按文件创建日期添加日期前缀 的映射函数"""
    pattern = build_date_prefix_pattern(date_format, sep)

    def mapper(path: str) -> str:
        name = os.path.basename(path)
        if pattern.match(name):
            # 已是当前格式的日期前缀, 避免重复叠加
            return name
        if fs_util.has_date_prefix(name):
            # 已有其它常见格式(如 2026-09-11_)的日期前缀, 同样不叠加
            return name
        create_time = fs_util.get_file_create_time(path)
        date_str = time.strftime(date_format, time.localtime(create_time))
        return add_date_prefix_name(name, date_str, sep)
    return mapper


def build_reformat_date_mapper(
    date_format: str = DEFAULT_DATE_FORMAT,
    sep: str = DEFAULT_DATE_SEP,
) -> Callable[[str], str]:
    """构造 重新格式化已有日期前缀 的映射函数

    只改写日期的写法 (如 2026-09-08_ => 20260908_), 日期之后的内容保持不变;
    没有可识别日期前缀的文件保持原名。
    """
    def mapper(path: str) -> str:
        name = os.path.basename(path)
        return fs_util.reformat_date_prefix(name, date_format, sep)
    return mapper


def build_remove_date_mapper(
    date_format: str = DEFAULT_DATE_FORMAT,
    sep: str = DEFAULT_DATE_SEP,
) -> Callable[[str], str]:
    """构造 删除日期前缀 的映射函数

    先按 --date-format 指定的格式删除; 没匹配上时再兜底识别常见日期格式
    (如 2026-09-11_ / 2026_09_11_ / 2026.09.11_), 避免换了格式就删不掉。
    """
    pattern = build_date_prefix_pattern(date_format, sep)

    def mapper(path: str) -> str:
        name = os.path.basename(path)
        stripped = strip_date_prefix_by_pattern(name, pattern)
        if stripped != name:
            return stripped
        return fs_util.strip_date_prefix(name)
    return mapper


def _decode_stdin_bytes(raw: bytes) -> str:
    """把管道输入的字节解码为文本, 自动识别常见编码

    * 带 BOM 的 UTF-16/UTF-8 (utf-8-sig 会自动去掉 BOM)
    * 无 BOM 的普通 UTF-8
    * 均失败时回退到系统本地编码
    """
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        encoding = sys.stdin.encoding or "utf-8"
        return raw.decode(encoding, errors="replace")


def read_stdin_files() -> List[str]:
    """从标准输入按行读取待处理的文件路径列表

    * 交互终端逐行读取; 管道输入自动识别 UTF-8/UTF-16 等编码
    * 每行一个文件路径, 自动去除首尾空白
    * 忽略空行与 `#` 开头的注释行
    """
    if sys.stdin.isatty():
        lines = sys.stdin
    else:
        raw = sys.stdin.buffer.read()
        lines = _decode_stdin_bytes(raw).splitlines()
    files: List[str] = []
    first_line = True
    for line in lines:
        fpath = line.strip()
        if first_line:
            # 某些管道会多带一个 BOM 字符, 只出现在输入开头
            fpath = fpath.lstrip("\ufeff").strip()
            first_line = False
        if fpath == "" or fpath.startswith("#"):
            continue
        files.append(fpath)
    return files


def collect_files(
    dirname: str,
    recursive: bool,
    use_stdin: bool,
) -> List[str]:
    """收集待处理的文件路径列表

    * use_stdin=True 时从标准输入读取(每行一个路径), 忽略 dirname/recursive
    * 否则扫描 dirname 目录(recursive=True 时递归子目录)
    """
    if use_stdin:
        return read_stdin_files()
    if not os.path.isdir(dirname):
        print("错误: 目录不存在: %s" % dirname, file=sys.stderr)
        sys.exit(1)
    try:
        return iter_files(dirname, recursive)
    except OSError as ex:
        print("错误: %s" % ex, file=sys.stderr)
        sys.exit(1)


def confirm_to_run(total: int) -> bool:
    """交互确认是否执行。stdin 非交互终端时无法确认, 返回 False(需用 -y 执行)。

    stdin 被占用(管道输入文件列表)等非交互场景一律不自动放行, 避免误执行。
    确认提示打印到 stderr, 避免 stdout 被重定向时看不到提示。
    """
    if not sys.stdin.isatty():
        print("标准输入非交互终端, 无法确认; 如需执行请加 -y/--yes 参数",
              file=sys.stderr)
        return False
    sys.stderr.write("是否执行以上 %s 项重命名? (y/n): " % total)
    sys.stderr.flush()
    try:
        answer = sys.stdin.readline()
    except KeyboardInterrupt:
        return False
    return answer.strip().lower() in ("y", "yes")


def batch_rename(
    files: List[str],
    mapper: Callable[[str], str],
    dry_run: bool,
    yes: bool,
) -> None:
    """按 mapper 对文件列表批量重命名: 先打印调整计划, 确认后再执行

    * mapper 入参为完整文件路径, 返回新文件名; 无变化则跳过
    * dry_run=True 时只打印调整计划, 不执行
    * yes=True 时跳过交互确认直接执行
    """
    plans: List[Tuple[str, str]] = []
    skipped = 0
    for old_path in files:
        old_name = os.path.basename(old_path)
        if not os.path.isfile(old_path):
            logging.warning("跳过(不存在或不是文件): %s", old_path)
            skipped += 1
            continue
        dirpath = os.path.dirname(old_path)
        try:
            new_name = mapper(old_path)
        except OSError as ex:
            logging.error("读取文件信息失败: %s - %s", old_path, ex)
            skipped += 1
            continue
        if new_name == old_name:
            skipped += 1
            continue
        new_path = os.path.join(dirpath, new_name)
        if os.path.exists(new_path):
            logging.warning("跳过(目标已存在): %s -> %s", old_path, new_path)
            skipped += 1
            continue
        plans.append((old_path, new_path))

    if not plans:
        print("没有需要重命名的文件(跳过 %s 个)" % skipped)
        return

    print("计划重命名 %s 个文件(跳过 %s 个):" % (len(plans), skipped))
    for index, (old_path, new_path) in enumerate(plans, start=1):
        print("  [%02d] %s" % (index, old_path))
        print("       -> %s" % new_path)

    if dry_run:
        print("预览模式(dry-run), 未执行任何操作")
        return

    if not yes and not confirm_to_run(len(plans)):
        print("操作已取消")
        return

    changed = 0
    for old_path, new_path in plans:
        try:
            os.rename(old_path, new_path)
            print("%s -> %s" % (old_path, new_path))
            changed += 1
        except OSError as ex:
            logging.error("重命名失败: %s - %s", old_path, ex)
            skipped += 1
    print("处理完成: 重命名 %s 个文件, 跳过 %s 个" % (changed, skipped))


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """为批量重命名命令添加公共参数"""
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="递归处理子目录中的文件")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="只打印调整计划, 不实际重命名")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="跳过交互确认直接执行")
    parser.add_argument("-i", "--stdin", action="store_true",
                        help="从标准输入按行读取待处理的文件列表, 代替扫描目录(忽略目录参数)")


def add_dir_args(parser: argparse.ArgumentParser) -> None:
    """为按路径处理的命令添加 目录 + 公共参数"""
    parser.add_argument("dirname", nargs="?", default="./",
                        help="目标目录(默认当前目录; -i 时该参数被忽略)")
    add_common_args(parser)


def add_batch_args(parser: argparse.ArgumentParser, text_help: str) -> None:
    """为前后缀增删命令添加公共参数"""
    parser.add_argument("dirname", nargs="?", default="./",
                        help="目标目录(默认当前目录; -i 时该参数被忽略)")
    parser.add_argument("text", help=text_help)
    add_common_args(parser)


def add_date_args(parser: argparse.ArgumentParser) -> None:
    """为日期前缀命令添加公共参数"""
    parser.add_argument("--date-format", default=DEFAULT_DATE_FORMAT,
                        help="日期格式(strftime令牌), 默认 %(default)s")
    parser.add_argument("--sep", default=DEFAULT_DATE_SEP,
                        help="日期与文件名之间的分隔符, 默认 %(default)r; 不需要分隔符时传空字符串")


if __name__ == "__main__":
    def new_parser(name: str, help_text: str, epilog: Optional[str] = None) -> argparse.ArgumentParser:
        """创建子命令解析器, 保留 epilog 中的换行与缩进"""
        return subparsers.add_parser(
            name,
            help=help_text,
            epilog=epilog,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

    parser = argparse.ArgumentParser(
        description="文件名批量编解码与前后缀/日期前缀增删工具;"
                    "重命名命令先打印计划并交互确认, 支持 -i 从管道读取文件列表",
        epilog=MAIN_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    encode_parser = new_parser(
        "encode", "对文件名进行base64编码",
        "示例: duck-rename encode ./data -d 2")
    encode_parser.add_argument("dirname", nargs="?", default="./", help="目录路径")
    encode_parser.add_argument(
        "-d", "--max-depth", type=int, default=DEFAULT_MAX_DEPTH,
        help="递归最大深度, 默认 %s" % DEFAULT_MAX_DEPTH)

    decode_parser = new_parser(
        "decode", "对文件名进行base64解码",
        "示例: duck-rename decode ./data")
    decode_parser.add_argument("dirname", nargs="?", default="./", help="目录路径")
    decode_parser.add_argument(
        "-d", "--max-depth", type=int, default=DEFAULT_MAX_DEPTH,
        help="递归最大深度, 默认 %s" % DEFAULT_MAX_DEPTH)

    add_prefix_parser = new_parser(
        "add-prefix", "批量添加文件前缀",
        "示例: duck-rename add-prefix ./photos img_ -n" + "\n" + PIPE_USAGE)
    add_batch_args(add_prefix_parser, "要添加的前缀文本")

    remove_prefix_parser = new_parser(
        "remove-prefix", "批量删除文件前缀",
        "示例: duck-rename remove-prefix ./photos img_ -y" + "\n" + PIPE_USAGE)
    add_batch_args(remove_prefix_parser, "要删除的前缀文本")

    add_suffix_parser = new_parser(
        "add-suffix", "批量添加文件后缀(扩展名之前)",
        "示例: duck-rename add-suffix ./photos _v2      # a.jpg -> a_v2.jpg\n"
        "      duck-rename add-suffix ./photos _bak -a  # a.jpg -> a.jpg_bak\n"
        + PIPE_USAGE)
    add_batch_args(add_suffix_parser, "要添加的后缀文本")
    add_suffix_parser.add_argument(
        "-a", "--after-ext", action="store_true",
        help="追加到扩展名之后(如 a.txt + _bak => a.txt_bak)")

    remove_suffix_parser = new_parser(
        "remove-suffix", "批量删除文件后缀(扩展名之前)",
        "示例: duck-rename remove-suffix ./photos _v2\n"
        "      duck-rename remove-suffix ./photos _bak -a\n" + PIPE_USAGE)
    add_batch_args(remove_suffix_parser, "要删除的后缀文本")
    remove_suffix_parser.add_argument(
        "-a", "--after-ext", action="store_true",
        help="从完整文件名末尾删除(对应 add-suffix --after-ext 的结果)")

    add_date_parser = new_parser(
        "add-date-prefix", "按文件创建日期批量添加日期前缀(如 20260908_xxx)")
    add_dir_args(add_date_parser)
    add_date_args(add_date_parser)

    remove_date_parser = new_parser(
        "remove-date-prefix", "批量删除文件日期前缀(与 add-date-prefix 参数对应)")
    add_dir_args(remove_date_parser)
    add_date_args(remove_date_parser)

    reformat_date_parser = new_parser(
        "reformat-date-prefix", "把已有的日期前缀重新格式化(如 2026-09-08_xxx => 20260908_xxx)")
    add_dir_args(reformat_date_parser)
    add_date_args(reformat_date_parser)

    args = parser.parse_args()
    if args.command == "encode":
        encode(args.dirname, args.max_depth)
    elif args.command == "decode":
        decode(args.dirname, args.max_depth)
    elif args.command in BATCH_COMMANDS or args.command in DATE_COMMANDS:
        if args.command in BATCH_COMMANDS:
            after_ext = bool(getattr(args, "after_ext", False))
            mapper = build_mapper(args.command, args.text, after_ext)
        elif args.command == "add-date-prefix":
            mapper = build_add_date_mapper(args.date_format, args.sep)
        elif args.command == "reformat-date-prefix":
            mapper = build_reformat_date_mapper(args.date_format, args.sep)
        else:  # remove-date-prefix
            mapper = build_remove_date_mapper(args.date_format, args.sep)
        files = collect_files(args.dirname, args.recursive, args.stdin)
        batch_rename(files, mapper, args.dry_run, args.yes)
    else:
        parser.print_help()
