# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/02/25 12:34:29
# @modified 2020/03/02 12:20:17
import sys
import argparse
import os
import time
import traceback
import json
import shutil
import subprocess
from typing import List, Optional

# 本文件负责触发 install/upgrade, 可能在 duck_utils 尚未安装或版本过旧(不含 duck_meta)
# 时运行, 因此优先把仓库根目录放到 sys.path 最前, 确保导入的是本地仓库的 duck_utils 副本,
# 而不依赖 venv 中已安装(可能陈旧)的副本。其它命令可假定 duck_utils 已安装最新版, 无需此处理。
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from duck_utils.duck_meta import InstallMeta
from duck_utils.os_util import get_duck_rush_home

EXECTABLE_FILE_EXT_SET = set([
    ".py", 
    ".sh", ".command", 
    ".bat", 
    ".exe",
    ".js",   # NodeJS
])

PATH_ESCAPE_CHARS = "^[]@*$!<> "

def print_red(msg):
    print("\033[31m\033[01m%s\033[0m" % msg, end = '')


def print_blue(msg):
    print("\033[34m\033[01m%s\033[0m" % msg, end = '')


def print_green(msg):
    print("\033[32m\033[01m%s\033[0m" % msg, end = '')


def print_lightblue(msg):
    print("\033[36m%s\033[0m" % msg, end = '')

def escape_arg(path):
    i = 0
    target = ''
    for c in path:
        if c in PATH_ESCAPE_CHARS:
            target += '\\' + c
        else:
            target += c
    return target

def log_debug(*args):
    print_lightblue("[DEBUG]")
    print(*args)
    # print("\033[36m[DEBUG]\033[0m", *args)

class DuckCommand:

    def __init__(self, fpath):
        self.fpath = fpath
        self.fname  = os.path.basename(fpath)
        self.name, self.ext = os.path.splitext(self.fname)

    def match(self, name):
        # TODO 相似度>90%
        return self.name.find(name) >= 0

    def execute(self, args):
        args = " ".join([escape_arg(arg) for arg in args])
        if self.ext == ".py":
            os.system("python3 %s %s" % (escape_arg(self.fpath), args))
        # 命令输出结束时补一个换行, 避免输出与 shell 的 prompt 混在同一行
        sys.stdout.write("\n")

def is_executable_file(fpath):
    name, ext = os.path.splitext(fpath)
    return ext in EXECTABLE_FILE_EXT_SET

COMMAND_EXT_SET = {".py", ".sh"}
SKIP_DIRS_FOR_LIST = {"web-tools", "gui-tools", "lib", "data", "local", "__pycache__"}


def get_external_src_dirs() -> List[str]:
    """返回已登记且仍然存在的外部工具源码目录列表 (读取 ~/.duck-rush/duck.json)。"""
    return InstallMeta.load().get_external_src_dirs()


def get_external_tools() -> List[str]:
    """返回已用 `duck add` 单独添加、且仍然存在的脚本原始路径列表。"""
    return InstallMeta.load().get_external_tools()


def get_command_list(extra_roots: Optional[List[str]] = None, extra_files: Optional[List[str]] = None) -> list:
    duck_dir = os.path.dirname(os.path.abspath(__file__))
    command_list = []
    roots = [duck_dir] + (extra_roots or [])
    for src_root in roots:
        if not os.path.isdir(src_root):
            continue
        is_main = (src_root == duck_dir)
        for root, dirs, files in os.walk(src_root):
            # 仅对主源码目录原地修剪非命令目录(Web工具/GUI/第三方库/数据/构建产物)
            if is_main:
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS_FOR_LIST]
            for fname in files:
                if fname == "duck.py" or fname.startswith("__") or fname.startswith("test_"):
                    continue
                name, ext = os.path.splitext(fname)
                if ext not in COMMAND_EXT_SET:
                    continue
                if fname.endswith("_util.py"):
                    # 跳过工具类模块
                    continue
                fpath = os.path.join(root, fname)
                command_list.append(DuckCommand(fpath))
    # 单独添加的外部脚本(原始路径, 不复制): 直接作为命令纳入
    for fpath in (extra_files or []):
        if os.path.isfile(fpath):
            command_list.append(DuckCommand(fpath))
    return command_list


def load_desc_cache() -> dict:
    """读取安装时生成的命令简介缓存 (data/install/command_desc.jsonl)。"""
    cache_file = os.path.join(get_project_root(), "data", "install", "command_desc.jsonl")
    cache: dict = {}
    if not os.path.exists(cache_file):
        return cache
    try:
        with open(cache_file, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                cache[obj.get("name", "")] = obj.get("desc", "")
    except Exception:
        return {}
    return cache


def save_desc_cache(cache: dict) -> None:
    """把简介缓存写回 data/install/command_desc.jsonl。"""
    cache_file = os.path.join(get_project_root(), "data", "install", "command_desc.jsonl")
    try:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as fp:
            for name, desc in cache.items():
                fp.write(json.dumps({"name": name, "desc": desc}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def get_desc_by_help(cmd: "DuckCommand", timeout: int = 3) -> str:
    """运行 {cmd} -h 提取首行非空内容作为简介; 超时或失败返回空串。"""
    if cmd.ext == ".py":
        cmdline = [sys.executable, cmd.fpath, "-h"]
    elif cmd.ext == ".sh":
        cmdline = ["bash", cmd.fpath, "-h"]
    else:
        return ""
    try:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["LC_ALL"] = "C.UTF-8"
        env["LANG"] = "C.UTF-8"
        proc = subprocess.run(
            cmdline,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            timeout=timeout,
        )
        out = proc.stdout.decode("utf-8", errors="replace")
    except Exception:
        return ""
    for line in out.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def list_command_func(args: argparse.Namespace) -> None:
    short = bool(args.short)
    commands = get_command_list(get_external_src_dirs(), get_external_tools())
    cache = load_desc_cache()
    need_save = False
    for cmd in commands:
        desc = cache.get(cmd.name)
        if desc is None:
            desc = get_desc_by_help(cmd)
            cache[cmd.name] = desc
            need_save = True
        if short:
            print(cmd.name)
        else:
            print("%s - %s" % (cmd.name, desc))
    if need_save:
        save_desc_cache(cache)

# 解析时未被 duck.py 识别、需要透传给子命令(如 install)的参数
_UNKNOWN_ARGS: List[str] = []


def _run_full_install() -> None:
    """运行完整安装 (install.py, 不附加任何参数)。

    完整安装会重新收集所有命令并清理 bin 目录下过期的包装脚本, 因此用于
    增加/移除外部源码目录或单脚本命令后, 使 duck.json 的登记与新生成的
    脚本链接保持一致。
    """
    install_script = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "install.py"))
    rc = os.system("%s %s" % (sys.executable, install_script))
    if rc != 0:
        sys.stderr.write("重新安装失败 (安装脚本退出码 %d)\n" % rc)
        sys.exit(1)


def install_func(args):
    install_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "install.py")
    install_script = os.path.normpath(install_script)
    extra = " ".join([escape_arg(a) for a in (args.args + _UNKNOWN_ARGS)])
    os.system("%s %s %s" % (sys.executable, install_script, extra))

def add_src_dir_func(args):
    """登记外部工具源码目录, 写入 ~/.duck-rush/duck.json 的 external_src_dirs,
    并立即重新安装以生成对应的脚本链接。
    """
    if not args.args:
        sys.stderr.write("用法: duck add-src-dir <外部工具源码目录>\n")
        sys.exit(1)
    raw = args.args[0]
    d = os.path.abspath(os.path.expanduser(raw))
    if not os.path.isdir(d):
        sys.stderr.write("目录不存在: %s\n" % d)
        sys.exit(1)

    meta = InstallMeta.load()
    if not meta.add_external_src_dir(d):
        print("外部源码目录已存在, 无需重复添加: %s" % d)
        return

    meta.save()
    print("已添加外部源码目录: %s" % d)
    print("正在重新安装以生成脚本链接 ...")
    install_func(args)

ADD_TOOL_USAGE = "用法: duck add <脚本路径> [<脚本路径> ...]\n" \
                  "  把单个 .py/.sh 脚本文件注册为 duck 工具:\n" \
                  "  .py: 不复制, 记录原始路径并在 ~/.duck-rush/bin 生成启动器\n" \
                  "       (Windows: .bat, 其它平台: bash) 直接执行源文件\n" \
                  "  .sh: 复制到 ~/.duck-rush/external-tools/ 并登记该目录\n" \
                  "  二者均登记到 duck.json, 重装/升级后依然生效"

def add_tool_func(args):
    """把单个脚本文件注册为 duck 工具(外部工具目录 + 包装脚本)。

    与 add-src-dir(整目录)不同, 这里只接收具体的脚本文件, 适合零散地
    把一两个现成脚本纳入 duck-rush 体系, 而不必专门建一个源码目录。

    Python 脚本不再复制, 而是把原始路径记入 duck.json 的 external_tools,
    由 install.py 生成指向源文件的启动器(.bat/.sh), 这样源文件更新后无需重新 add。
    """
    if args.args and args.args[0] in ("-h", "--help"):
        print(ADD_TOOL_USAGE)
        return
    if not args.args:
        sys.stderr.write(ADD_TOOL_USAGE + "\n")
        sys.exit(1)

    meta = InstallMeta.load()
    ext_dir = os.path.join(get_duck_rush_home(), "external-tools")

    installed: List[str] = []
    for raw in args.args:
        src = os.path.abspath(os.path.expanduser(raw))
        if not os.path.isfile(src):
            sys.stderr.write("文件不存在: %s\n" % src)
            continue
        ext = os.path.splitext(src)[1].lower()
        if ext not in (".py", ".sh"):
            sys.stderr.write("仅支持 .py / .sh 脚本: %s\n" % src)
            continue
        name = os.path.splitext(os.path.basename(src))[0]
        if ext == ".py":
            # Python 不复制: 记录原始路径, install.py 据此生成指向源文件的启动器
            if meta.add_external_tool(src):
                meta.save()
            installed.append(name)
            print("已登记脚本(不复制, 生成启动器): %s" % src)
        else:
            # shell 脚本沿用复制策略, 复制到外部工具目录并登记
            if meta.add_external_src_dir(ext_dir):
                meta.save()
            os.makedirs(ext_dir, exist_ok=True)
            dest = os.path.join(ext_dir, os.path.basename(src))
            # 同一文件重复 add 时覆盖, 便于更新脚本后刷新包装脚本
            shutil.copy2(src, dest)
            installed.append(name)
            print("已复制脚本: %s -> %s" % (src, dest))

    if not installed:
        sys.stderr.write("没有可注册的脚本, 未生成任何包装脚本\n")
        sys.exit(1)

    # 仅安装这些命令的包装脚本(直接复用 install.py 的按名安装能力)
    install_script = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "install.py"))
    targets = " ".join(escape_arg(name) for name in installed)
    rc = os.system("%s %s %s" % (sys.executable, install_script, targets))
    if rc != 0:
        sys.stderr.write("生成包装脚本失败(安装脚本退出码 %d)\n" % rc)
        sys.exit(1)

RM_SRC_DIR_USAGE = "用法: duck rm-src-dir <外部工具源码目录>\n" \
                   "  移除已用 `duck add-src-dir` 登记的外部工具源码目录:\n" \
                   "  从 duck.json 删除登记项, 并重新安装以清理 bin 下对应的过期脚本链接\n" \
                   "  仅移除登记, 不会删除该目录或其下的源文件"

def _match_external_src_dirs(registered: List[str], raw: str) -> List[str]:
    """在已登记的外部源码目录中, 按绝对路径精确匹配; 无精确命中时退回按目录名匹配。

    返回需要移除的登记项列表 (可能为空)。
    """
    target = os.path.abspath(os.path.expanduser(raw))
    norm_target = target.rstrip(os.sep)
    exact = [d for d in registered if os.path.abspath(os.path.expanduser(d)) == target]
    if exact:
        return exact
    # 精确未命中: 用目录名兜底, 便于 `duck rm-src-dir my-tools` 这类简写
    base = os.path.basename(norm_target)
    if base:
        return [d for d in registered if os.path.basename(d.rstrip(os.sep)) == base]
    return []

def rm_src_dir_func(args: argparse.Namespace) -> None:
    """移除已登记的外部工具源码目录, 并重新安装以清理对应的脚本链接。

    与 add-src-dir(整目录)对称: 仅删除 duck.json 中的登记项, 不触碰源目录自身。
    """
    if args.args and args.args[0] in ("-h", "--help"):
        print(RM_SRC_DIR_USAGE)
        return
    if not args.args:
        sys.stderr.write(RM_SRC_DIR_USAGE + "\n")
        sys.exit(1)

    raw = args.args[0]
    meta = InstallMeta.load()
    matches = _match_external_src_dirs(meta.external_src_dirs, raw)
    if not matches:
        sys.stderr.write("未找到已登记的外部源码目录: %s\n" % raw)
        sys.exit(1)

    for d in matches:
        meta.remove_external_src_dir(d)
    meta.save()
    print("已移除外部源码目录登记: %s" % ", ".join(matches))
    print("正在重新安装以清理脚本链接 ...")
    _run_full_install()

RM_TOOL_USAGE = "用法: duck rm <命令名> [<命令名> ...]\n" \
                "  移除已用 `duck add` 单独添加的单脚本命令:\n" \
                "  .py: 从 duck.json 删除原始路径登记 (不删除源文件)\n" \
                "  .sh: 删除复制到 ~/.duck-rush/external-tools/ 的副本, 并在该目录变空时注销它\n" \
                "  二者均重新安装以清理 bin 下对应的过期包装脚本"

def rm_tool_func(args: argparse.Namespace) -> None:
    """移除已用 `duck add` 单独添加的单脚本命令, 并清理对应包装脚本。

    仅针对外部添加的命令: .py 不复制(只删登记), .sh 复制自外部工具目录(删副本)。
    不删除用户自己的原始脚本文件; 移除后重新安装以清理 bin 下的过期脚本链接。
    """
    if args.args and args.args[0] in ("-h", "--help"):
        print(RM_TOOL_USAGE)
        return
    if not args.args:
        sys.stderr.write(RM_TOOL_USAGE + "\n")
        sys.exit(1)

    names = list(args.args)
    meta = InstallMeta.load()
    ext_dir = os.path.join(get_duck_rush_home(), "external-tools")
    removed: List[str] = []

    for name in names:
        # 不复制的 .py: 从 external_tools 中按命令名移除原始路径登记
        for p in list(meta.external_tools):
            if os.path.splitext(os.path.basename(p))[0] == name:
                meta.remove_external_tool(p)
                if name not in removed:
                    removed.append(name)
        # 复制到 external-tools 的 .sh / .py 副本: 直接删除文件
        for ext in (".sh", ".py"):
            copied = os.path.join(ext_dir, name + ext)
            if os.path.isfile(copied):
                os.remove(copied)
                if name not in removed:
                    removed.append(name)

    # 若 external-tools 目录变空, 注销该目录登记并删掉空目录
    if os.path.isdir(ext_dir) and not os.listdir(ext_dir):
        if ext_dir in meta.external_src_dirs:
            meta.remove_external_src_dir(ext_dir)
        os.rmdir(ext_dir)

    if not removed:
        sys.stderr.write("未找到已登记的外部命令: %s\n" % ", ".join(names))
        sys.exit(1)

    meta.save()
    print("已移除外部命令: %s" % ", ".join(removed))
    print("正在重新安装以清理脚本链接 ...")
    _run_full_install()

def upgrade_func(args):
    project_root = get_project_root()
    os.chdir(project_root)
    # git 同步失败则直接中止, 不继续执行后续安装, 避免基于陈旧/冲突代码误安装
    rc = subprocess.run(["git", "pull"]).returncode
    if rc != 0:
        sys.stderr.write(
            "git pull 失败 (退出码 %d), 已中止升级, 未继续执行安装。\n" % rc)
        sys.exit(rc if rc > 0 else 1)
    install_func(args)

def get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def dir_func(args):
    project_root = get_project_root()
    print(project_root)

META_USAGE = "用法: duck meta [-h|--help]\n" \
             "  展示安装元数据 (~/.duck-rush/duck.json) 的关键信息:\n" \
             "  version / install_dir / bin_dir / data_dir / python / src_dir\n" \
             "  以及已登记的外部源码目录(external_src_dirs)与单独添加的外部脚本(external_tools)"

def meta_func(args):
    """展示安装元数据 (~/.duck-rush/duck.json), 直接以 JSON 输出。"""
    if args.args and args.args[0] in ("-h", "--help"):
        print(META_USAGE)
        return
    meta = InstallMeta.load()
    print(json.dumps(meta.to_dict(), ensure_ascii=False, indent=2))

def help_func(args):
    # `duck help -h` / `duck h -h` 仅打印用法, 不得启动 TUI (无副作用)
    if args.args and args.args[0] in ("-h", "--help"):
        PARSER.print_help()
        return
    # 启动交互式帮助浏览器 (duck-help), 交接终端, 退出后返回
    here = os.path.dirname(os.path.abspath(__file__))
    help_script = os.path.normpath(os.path.join(here, "shell", "duck-help.py"))
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["LC_ALL"] = "C.UTF-8"
    env["LANG"] = "C.UTF-8"
    subprocess.run([sys.executable, help_script], env=env)

def default_func(args):
    action = args.action
    log_debug(args)
    commands = get_command_list(get_external_src_dirs(), get_external_tools())
    matches  = []
    for cmd in commands:
        if cmd.match(action):
            matches.append(cmd)

    if len(matches) == 0:
        print("No command found")
        return

    if len(matches) == 1:
        return matches[0].execute(args.args)

    print("found multi commands:")
    for index, cmd in enumerate(matches):
        print("%02d: %s" % (index, cmd.name))

    try:
        choice = int(input("please choose: "))
    except (ValueError, EOFError):
        # 非交互环境(管道/重定向)或非法输入时退出, 不执行任何命令
        return
    if 0 <= choice < len(matches):
        matches[choice].execute(args.args)




ACTION_FUNC_DICT = {
    "list": list_command_func,
    "install": install_func,
    "upgrade": upgrade_func,
    "add-src-dir": add_src_dir_func,
    "add": add_tool_func,
    "rm-src-dir": rm_src_dir_func,
    "rm": rm_tool_func,
    "dir": dir_func,
    "meta": meta_func,
    "help": help_func,
    "h": help_func,
}

ACTION_DESC = {
    "list": "列出所有已注册命令 (支持 -s/--short 只打印命令名称)",
    "install": "安装全部工具: 装依赖 -> 安装 duck_utils -> 生成命令包装脚本 -> 生成命令简介缓存; 也可 `duck install <命令>` 只安装指定命令",
    "upgrade": "拉取最新代码 (git pull) 并重新安装",
    "add-src-dir": "登记外部工具源码目录, 更新 duck.json 并重新生成脚本链接",
    "add": "把单个脚本文件(.py/.sh)注册为 duck 工具: 复制到外部工具目录、登记并生成包装脚本",
    "rm-src-dir": "移除已登记的外部工具源码目录(只删 duck.json 登记, 不删源文件), 并重装清理脚本链接",
    "rm": "移除已用 duck add 添加的单脚本命令(.py 删登记/.sh 删副本), 并重装清理包装脚本",
    "dir": "打印 duck-rush 项目根目录的绝对路径",
    "meta": "展示安装元数据 (~/.duck-rush/duck.json) 的关键信息",
    "help": "进入交互式帮助浏览器 (TUI): 方向键浏览全部 duck-* 工具, Enter 启动, `/` 筛选",
    "h": "help 的别名, 进入交互式帮助浏览器 (TUI)",
}

EPILOG = (
    "可用操作 (action):\n"
    + "\n".join("  %-12s %s" % (name, ACTION_DESC.get(name, "")) for name in ACTION_FUNC_DICT)
    + "\n\n示例:\n"
    + "  duck list                      列出所有命令\n"
    + "  duck list -s                   只打印命令名称\n"
    + "  duck <命令>                    执行某个命令 (如: duck duck-json -h)\n"
    + "  duck dir                       打印项目根目录\n"
    + "  duck meta                      展示安装元数据 (~/.duck-rush/duck.json)\n"
    + "  duck help                      进入交互式帮助浏览器 (TUI), 方向键浏览并启动工具\n"
    + "  duck h                         同 duck help\n"
    + "  duck add-src-dir ~/my-tools   登记外部工具源码目录并生成脚本链接\n"
    + "  duck add ~/my-tool.py         把单个脚本文件注册为命令(生成其包装脚本)\n"
    + "  duck rm-src-dir ~/my-tools    移除已登记的外部源码目录并清理脚本链接\n"
    + "  duck rm my-tool               移除已用 duck add 添加的单脚本命令并清理包装脚本\n"
    + "  duck install <命令>           只安装指定命令(生成其包装脚本, 跳过完整安装)\n"
)

PARSER = argparse.ArgumentParser(
    description = "duck-rush 工具集入口",
    epilog = EPILOG,
    formatter_class = argparse.RawDescriptionHelpFormatter,
)
PARSER.add_argument("action", nargs = "?", help = "操作 (list/install/upgrade/dir/meta/help/h)", default = None)
PARSER.add_argument("args", nargs = "*", help = "参数")
PARSER.add_argument("-s", "--short", action = "store_true", help = "list 模式: 只打印命令名称, 不打印简介")

def main():
    args, unknown = PARSER.parse_known_args()
    global _UNKNOWN_ARGS
    _UNKNOWN_ARGS = unknown
    # `duck` 无参 或 `duck -h/--help`: 打印纯文本帮助(非交互, 可安全管道/脚本化), 不进入 TUI
    if args.action is None or args.action in ("-h", "--help"):
        PARSER.print_help()
        return
    func = ACTION_FUNC_DICT.get(args.action, default_func)
    func(args)

if __name__ == '__main__':
    main()