# -*- coding: utf-8 -*-
"""duck-ls —— 跨平台复刻 ls 的基础功能, 用于兼容非 unix 平台。

用法:
  duck-ls [选项] [路径...]

选项:
  -l              长格式: 权限 链接数 属主 属组 大小 修改时间 名称
  -a              显示全部条目(含隐藏文件)
  -A              同 -a, 但不显示 . 与 ..
  -h              大小以人类可读方式显示(K/M/G/T), 需配合 -l
  -t              按修改时间排序(新的在前)
  -S              按文件大小排序(大的在前)
  -r              反转排序结果
  -1              每行只输出一个条目
  -d              列出目录本身而不是目录内容
  --color[=WHEN]  上色; WHEN 为 always/auto/never, 省略 WHEN 等价于 always
  --no-color      等价于 --color=never
  --help          显示本帮助

说明:
  - 关于 -h: 作为**第一个参数**时(`duck-ls -h`)表示打印本帮助并退出, 这是 duck-rush
    对所有命令的统一约定(安装时会执行 `{cmd} -h` 采集命令简介)。在组合选项中
    (如 `duck-ls -lh`)或非首位时(如 `duck-ls -l -h`), -h 表示 ls 原本的
    「人类可读大小」语义。
  - 未指定 --color 时默认 auto: 仅当输出是终端时上色, 重定向/管道时不上色。
  - 非 -l 模式下按终端宽度多列输出; 输出到管道时自动改为每行一个。

示例:
  duck-ls                     # 多列列出当前目录
  duck-ls -lh --color         # 长格式 + 人类可读大小 + 上色
  duck-ls -la /tmp            # 含隐藏文件地列出 /tmp
  duck-ls -lt --color=never   # 按时间排序且不上色
"""
import argparse
import importlib
import os
import shutil
import stat
import sys
import time
import unicodedata
from typing import List, NamedTuple, Optional, Tuple

# 明亮色 ANSI 转义(深色背景下可读性更好); 不用 termcolor, 避免其版本间
# light_* 颜色名不兼容的问题。
COLOR_RESET = "\033[0m"
COLOR_DIR = "\033[94m"      # 明亮蓝: 目录
COLOR_LINK = "\033[96m"     # 明亮青: 符号链接
COLOR_EXEC = "\033[92m"     # 明亮绿: 可执行文件
COLOR_ARCHIVE = "\033[91m"  # 明亮红: 压缩包
COLOR_MEDIA = "\033[95m"    # 明亮品红: 图片/音视频

ARCHIVE_EXT = frozenset([
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".whl",
])
MEDIA_EXT = frozenset([
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico",
    ".mp3", ".wav", ".flac", ".mp4", ".mkv", ".avi", ".mov",
])
# Windows 没有可执行位, 按扩展名判断
WIN_EXEC_EXT = frozenset([".exe", ".bat", ".cmd", ".com", ".ps1"])

# 固定英文月份缩写: Windows 中文 locale 下 strftime("%b") 会输出「8月」, 破坏列对齐
MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
# 超过半年的文件显示年份而不是时分(与 ls 一致)
RECENT_SECONDS = 180 * 24 * 3600

COLOR_WHENS = ("always", "auto", "never")


class Entry(NamedTuple):
    """一个待展示的目录条目。"""
    name: str
    path: str
    st: os.stat_result
    is_dir: bool
    is_link: bool
    link_target: str


class Options(NamedTuple):
    """渲染选项(避免在函数间传递过多位置参数)。"""
    long_format: bool
    human: bool
    one_per_line: bool
    color: bool


def is_windows() -> bool:
    return os.name == "nt"


# ---------------------------------------------------------------------- #
# 大小 / 时间 / 宽度 等格式化
# ---------------------------------------------------------------------- #
def format_size(size: int, human: bool = False) -> str:
    """格式化文件大小。human=False 时返回原始字节数。

    >>> format_size(1023, True)
    '1023'
    >>> format_size(1024, True)
    '1.0K'
    >>> format_size(1536, True)
    '1.5K'
    >>> format_size(1048576, True)
    '1.0M'
    """
    if not human:
        return str(size)
    if size < 1024:
        return str(size)
    value = float(size)
    for unit in ("K", "M", "G", "T", "P"):
        value /= 1024
        if value < 1024:
            # 小于 10 时保留一位小数(1.5K), 否则取整(23K), 与 ls -h 观感一致
            if value < 10:
                return "%.1f%s" % (value, unit)
            return "%d%s" % (round(value), unit)
    return "%.1fE" % value


def format_mtime(mtime: float, now: Optional[float] = None) -> str:
    """格式化修改时间: 近半年为 `Aug 23 14:05`, 更早为 `Aug 23  2024`。"""
    if now is None:
        now = time.time()
    tm = time.localtime(mtime)
    month = MONTH_ABBR[tm.tm_mon - 1]
    if abs(now - mtime) <= RECENT_SECONDS:
        return "%s %2d %02d:%02d" % (month, tm.tm_mday, tm.tm_hour, tm.tm_min)
    return "%s %2d  %4d" % (month, tm.tm_mday, tm.tm_year)


def display_width(text: str) -> int:
    """计算字符串在终端的显示宽度(中日韩全角字符占 2 列)。

    >>> display_width("abc")
    3
    >>> display_width("中文")
    4
    >>> display_width("a中")
    3
    """
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            # 组合字符(如声调符号)不占额外宽度
            continue
        if unicodedata.east_asian_width(ch) in ("W", "F"):
            width += 2
        else:
            width += 1
    return width


def pad_to_width(text: str, width: int) -> str:
    """按显示宽度右侧补空格(不能用 str.ljust, 它按字符数而非显示宽度)。"""
    padding = width - display_width(text)
    if padding <= 0:
        return text
    return text + " " * padding


def get_owner_group(st: os.stat_result) -> Tuple[str, str]:
    """返回 (属主, 属组)。Windows 无 pwd/grp 概念, 统一回退为 `-`。

    用 importlib 动态导入而非 `import pwd`: pwd/grp 只有 unix 平台的类型存根,
    在 Windows 上做静态检查时直接 import 会报找不到模块。
    """
    if is_windows():
        return "-", "-"
    owner = str(st.st_uid)
    group = str(st.st_gid)
    try:
        pwd = importlib.import_module("pwd")
        owner = str(pwd.getpwuid(st.st_uid).pw_name)
    except (ImportError, KeyError):
        pass
    try:
        grp = importlib.import_module("grp")
        group = str(grp.getgrgid(st.st_gid).gr_name)
    except (ImportError, KeyError):
        pass
    return owner, group


# ---------------------------------------------------------------------- #
# 上色
# ---------------------------------------------------------------------- #
def ensure_pipe_newline() -> None:
    """Windows 下管道输出只用 \\n 换行。

    Windows 的文本模式会把 \\n 翻译成 \\r\\n, 经管道传给 grep/xargs 时文件名尾部会
    带上 \\r, 导致下游报「找不到文件」。仅在非终端(即被重定向/管道)时调整,
    终端输出保持原样。
    """
    if sys.platform != "win32" or sys.stdout.isatty():
        return
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(newline="\n")


def enable_windows_ansi() -> None:
    """Windows 下开启控制台的 VT 转义处理, 否则 ANSI 颜色会显示成乱码。

    Win10 1511+ 的 conhost 支持 VT, 但需要显式打开 ENABLE_VIRTUAL_TERMINAL_PROCESSING;
    Windows Terminal 默认已开启, 重复设置也无害。任何一步失败都静默跳过。
    """
    if not is_windows():
        return
    try:
        import ctypes
        windll = getattr(ctypes, "windll", None)
        kernel32 = getattr(windll, "kernel32", None) if windll is not None else None
        if kernel32 is None:
            return
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return
        kernel32.SetConsoleMode(handle, mode.value | 0x4)
    except Exception:  # noqa: ctypes 不可用时不上色也能正常工作
        pass


def is_executable(entry: Entry) -> bool:
    if entry.is_dir:
        return False
    if is_windows():
        return os.path.splitext(entry.name)[1].lower() in WIN_EXEC_EXT
    return os.access(entry.path, os.X_OK)


def pick_color(entry: Entry) -> str:
    """返回该条目对应的 ANSI 颜色前缀, 无需上色时返回空串。"""
    if entry.is_link:
        return COLOR_LINK
    if entry.is_dir:
        return COLOR_DIR
    if is_executable(entry):
        return COLOR_EXEC
    ext = os.path.splitext(entry.name)[1].lower()
    if ext in ARCHIVE_EXT:
        return COLOR_ARCHIVE
    if ext in MEDIA_EXT:
        return COLOR_MEDIA
    return ""


def colorize(entry: Entry, enabled: bool) -> str:
    """给条目名上色。补齐对齐必须基于未上色的 entry.name, 故上色总是最后一步。"""
    if not enabled:
        return entry.name
    color = pick_color(entry)
    if not color:
        return entry.name
    return color + entry.name + COLOR_RESET


# ---------------------------------------------------------------------- #
# 条目收集 / 过滤 / 排序
# ---------------------------------------------------------------------- #
def is_hidden(name: str, path: str) -> bool:
    """隐藏条目判定: unix 看 `.` 前缀; Windows 额外识别隐藏属性。"""
    if name.startswith("."):
        return True
    if not is_windows():
        return False
    try:
        attrs = getattr(os.stat(path), "st_file_attributes", 0)
    except OSError:
        return False
    # 用 getattr 取常量: FILE_ATTRIBUTE_HIDDEN 只在 Windows 平台的类型存根里,
    # 直接引用会让其他平台的静态检查报错
    hidden_flag = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0x2)
    return bool(attrs & hidden_flag)


def make_entry(name: str, path: str) -> Optional[Entry]:
    """构造 Entry; 无法 stat(权限不足/断链)时返回 None。"""
    try:
        st = os.lstat(path)
    except OSError:
        return None
    is_link = stat.S_ISLNK(st.st_mode)
    target = ""
    if is_link:
        try:
            target = os.readlink(path)
        except OSError:
            target = ""
        # 断链时 os.stat 会失败, 此时按链接本身的信息展示
        try:
            st_target = os.stat(path)
            is_dir = stat.S_ISDIR(st_target.st_mode)
        except OSError:
            is_dir = False
    else:
        is_dir = stat.S_ISDIR(st.st_mode)
    return Entry(name=name, path=path, st=st, is_dir=is_dir,
                 is_link=is_link, link_target=target)


def collect_dir(dirname: str, show_all: bool, almost_all: bool) -> List[Entry]:
    """列出目录内容。show_all 时补上 `.` 与 `..`(almost_all 则不补)。"""
    entries: List[Entry] = []
    if show_all and not almost_all:
        for dot in (".", ".."):
            entry = make_entry(dot, os.path.join(dirname, dot))
            if entry is not None:
                entries.append(entry)
    for name in os.listdir(dirname):
        path = os.path.join(dirname, name)
        if not (show_all or almost_all) and is_hidden(name, path):
            continue
        entry = make_entry(name, path)
        if entry is not None:
            entries.append(entry)
    return entries


def sort_entries(entries: List[Entry], by_time: bool, by_size: bool,
                 reverse: bool) -> List[Entry]:
    """排序: 默认按名称(忽略大小写), -t 按时间新→旧, -S 按体积大→小; -r 反转。

    -t / -S 默认已是降序(排序键取负), 所以 reverse 只在最后统一取反, 与 ls 一致。
    """
    if by_time:
        result = sorted(entries, key=lambda e: -e.st.st_mtime)
    elif by_size:
        result = sorted(entries, key=lambda e: -e.st.st_size)
    else:
        result = sorted(entries, key=lambda e: (e.name.lower(), e.name))
    if reverse:
        result.reverse()
    return result


# ---------------------------------------------------------------------- #
# 渲染
# ---------------------------------------------------------------------- #
def render_long(entries: List[Entry], opts: Options) -> List[str]:
    """长格式渲染: 各列宽度按本批条目的最大值对齐。"""
    rows: List[Tuple[str, str, str, str, str, str, str]] = []
    for entry in entries:
        owner, group = get_owner_group(entry.st)
        name = colorize(entry, opts.color)
        if entry.is_link and entry.link_target:
            name = "%s -> %s" % (name, entry.link_target)
        rows.append((
            stat.filemode(entry.st.st_mode),
            str(entry.st.st_nlink),
            owner,
            group,
            format_size(entry.st.st_size, opts.human),
            format_mtime(entry.st.st_mtime),
            name,
        ))
    if not rows:
        return []
    w_nlink = max(len(r[1]) for r in rows)
    w_owner = max(display_width(r[2]) for r in rows)
    w_group = max(display_width(r[3]) for r in rows)
    w_size = max(len(r[4]) for r in rows)
    lines: List[str] = []
    for mode, nlink, owner, group, size, mtime, name in rows:
        lines.append("%s %*s %s %s %*s %s %s" % (
            mode, w_nlink, nlink,
            pad_to_width(owner, w_owner), pad_to_width(group, w_group),
            w_size, size, mtime, name,
        ))
    return lines


def render_columns(entries: List[Entry], opts: Options,
                   term_width: int) -> List[str]:
    """多列渲染(列优先: 先竖着填满一列再换下一列, 与 ls 一致)。"""
    if not entries:
        return []
    names = [e.name for e in entries]
    colored = [colorize(e, opts.color) for e in entries]
    if opts.one_per_line:
        return colored

    gap = 2
    max_width = max(display_width(n) for n in names)
    # 每列宽度相同(含列间距), 由此推算能放几列
    columns = max(1, (term_width + gap) // (max_width + gap))
    if columns == 1:
        return colored
    total = len(entries)
    # 列优先布局: 行数向上取整, 最后一列可能不满
    rows = (total + columns - 1) // columns
    # 行数确定后重新压缩列数, 避免出现空列
    columns = (total + rows - 1) // rows

    # 逐列计算实际宽度, 比统一用全局最大宽度更紧凑
    col_widths: List[int] = []
    for col in range(columns):
        start = col * rows
        chunk = names[start:start + rows]
        col_widths.append(max(display_width(n) for n in chunk) if chunk else 0)

    lines: List[str] = []
    for row in range(rows):
        parts: List[str] = []
        for col in range(columns):
            index = col * rows + row
            if index >= total:
                continue
            is_last = (col == columns - 1) or (col * rows + rows + row >= total)
            if is_last:
                parts.append(colored[index])
            else:
                pad = col_widths[col] + gap - display_width(names[index])
                parts.append(colored[index] + " " * max(pad, 1))
        line = "".join(parts).rstrip()
        if line:
            lines.append(line)
    return lines


def render(entries: List[Entry], opts: Options, term_width: int) -> List[str]:
    if opts.long_format:
        return render_long(entries, opts)
    return render_columns(entries, opts, term_width)


# ---------------------------------------------------------------------- #
# 参数解析
# ---------------------------------------------------------------------- #
def extract_color_mode(argv: List[str]) -> Tuple[List[str], str]:
    """从参数中摘出颜色选项, 返回 (剩余参数, WHEN)。

    argparse 的 `nargs="?"` 会把 `--color /tmp` 里的 /tmp 当成选项值(真实 ls 可用),
    所以颜色选项在交给 argparse 之前先自行摘除。`--` 之后的内容视为文件名, 不再解析。

    >>> extract_color_mode(["-l", "--color"])
    (['-l'], 'always')
    >>> extract_color_mode(["--color=never", "x"])
    (['x'], 'never')
    >>> extract_color_mode(["--", "--color"])
    (['--', '--color'], 'auto')
    """
    mode = "auto"
    rest: List[str] = []
    end_of_options = False
    for arg in argv:
        if end_of_options:
            rest.append(arg)
            continue
        if arg == "--":
            end_of_options = True
            rest.append(arg)
        elif arg == "--color":
            mode = "always"
        elif arg.startswith("--color="):
            mode = arg.split("=", 1)[1]
        elif arg == "--no-color":
            mode = "never"
        else:
            rest.append(arg)
    return rest, mode


def build_parser() -> argparse.ArgumentParser:
    """构造解析器。

    add_help=False 是必需的: -h 要留给 ls 的「人类可读大小」语义(以支持 -lh),
    帮助由 main() 开头的守卫与手工声明的 --help 负责。
    """
    parser = argparse.ArgumentParser(
        prog="duck-ls",
        add_help=False,
        description="跨平台复刻 ls 的基础功能",
        epilog="颜色: --color[=always|auto|never] / --no-color (默认 auto)",
    )
    parser.add_argument("paths", nargs="*", help="要列出的文件或目录(默认当前目录)")
    parser.add_argument("-l", action="store_true", dest="long_format",
                        help="长格式输出")
    parser.add_argument("-a", action="store_true", dest="show_all",
                        help="显示全部条目(含 . 与 ..)")
    parser.add_argument("-A", action="store_true", dest="almost_all",
                        help="显示隐藏条目但不含 . 与 ..")
    parser.add_argument("-h", action="store_true", dest="human",
                        help="大小以人类可读方式显示(配合 -l)")
    parser.add_argument("-t", action="store_true", dest="by_time",
                        help="按修改时间排序(新的在前)")
    parser.add_argument("-S", action="store_true", dest="by_size",
                        help="按文件大小排序(大的在前)")
    parser.add_argument("-r", action="store_true", dest="reverse",
                        help="反转排序结果")
    parser.add_argument("-1", action="store_true", dest="one_per_line",
                        help="每行只输出一个条目")
    parser.add_argument("-d", action="store_true", dest="dir_itself",
                        help="列出目录本身而不是其内容")
    parser.add_argument("--help", action="help", help="显示帮助并退出")
    return parser


# ---------------------------------------------------------------------- #
# 主流程
# ---------------------------------------------------------------------- #
class Lister:
    """把命令行参数落成实际输出。"""

    def __init__(self, args: argparse.Namespace, opts: Options) -> None:
        self.args = args
        self.opts = opts
        self.term_width = shutil.get_terminal_size((80, 24)).columns
        self.exit_code = 0

    def run(self, paths: List[str]) -> int:
        files: List[Entry] = []
        dirs: List[str] = []
        for path in paths:
            # 展开 ~ 与 ~user(系统 shell 会自动做, 但本脚本不会, 否则
            # `duck-ls ~/foo` 会误报「不存在」); 真实路径不含 ~ 时原样返回
            path = os.path.expanduser(path)
            if not os.path.exists(path) and not os.path.islink(path):
                sys.stderr.write("duck-ls: 无法访问 '%s': 文件或目录不存在\n" % path)
                self.exit_code = 2
                continue
            if os.path.isdir(path) and not os.path.islink(path) \
                    and not self.args.dir_itself:
                dirs.append(path)
            else:
                # 文件操作数按用户给的原样展示(ls 亦如此), 不取 basename
                entry = make_entry(path, path)
                if entry is None:
                    sys.stderr.write("duck-ls: 无法读取 '%s'\n" % path)
                    self.exit_code = 2
                else:
                    files.append(entry)

        printed = False
        if files:
            self._print_entries(files)
            printed = True
        # 多个操作数时逐个目录加标题, 便于区分归属
        need_header = (len(dirs) + (1 if files else 0)) > 1
        for dirname in dirs:
            if printed:
                sys.stdout.write("\n")
            if need_header:
                sys.stdout.write("%s:\n" % dirname)
            self._print_dir(dirname)
            printed = True
        return self.exit_code

    def _print_dir(self, dirname: str) -> None:
        try:
            entries = collect_dir(dirname, self.args.show_all, self.args.almost_all)
        except OSError as e:
            sys.stderr.write("duck-ls: 无法打开目录 '%s': %s\n" % (dirname, e))
            self.exit_code = 2
            return
        self._print_entries(entries)

    def _print_entries(self, entries: List[Entry]) -> None:
        ordered = sort_entries(entries, self.args.by_time, self.args.by_size,
                               self.args.reverse)
        for line in render(ordered, self.opts, self.term_width):
            sys.stdout.write(line + "\n")


def main() -> None:
    # -h/--help 作为首个参数时打印帮助并退出, 不产生任何副作用
    # (安装时会执行 `duck-ls -h` 采集命令简介, 详见 install.py 的 generate_command_desc)
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    ensure_pipe_newline()
    argv, color_when = extract_color_mode(sys.argv[1:])
    if color_when not in COLOR_WHENS:
        sys.stderr.write("duck-ls: --color 取值无效: %s (可选 %s)\n"
                         % (color_when, "/".join(COLOR_WHENS)))
        sys.exit(2)

    parser = build_parser()
    args = parser.parse_args(argv)

    use_color = color_when == "always" or (
        color_when == "auto" and sys.stdout.isatty())
    if use_color:
        enable_windows_ansi()
    # 输出到管道/文件时改为每行一个, 便于下游按行处理(与 ls 行为一致)
    one_per_line = args.one_per_line or not sys.stdout.isatty()
    opts = Options(
        long_format=args.long_format,
        human=args.human,
        one_per_line=one_per_line,
        color=use_color,
    )

    paths = args.paths or ["."]
    lister = Lister(args, opts)
    sys.exit(lister.run(paths))


if __name__ == "__main__":
    main()
