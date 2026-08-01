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
import subprocess
from typing import List, Optional

# 本文件负责触发 install/upgrade, 可能在 duck_utils 尚未安装或版本过旧(不含 duck_meta)
# 时运行, 因此优先把仓库根目录放到 sys.path 最前, 确保导入的是本地仓库的 duck_utils 副本,
# 而不依赖 venv 中已安装(可能陈旧)的副本。其它命令可假定 duck_utils 已安装最新版, 无需此处理。
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from duck_utils.duck_meta import InstallMeta

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
        # print("execute %s" % self.fpath)

def is_executable_file(fpath):
    name, ext = os.path.splitext(fpath)
    return ext in EXECTABLE_FILE_EXT_SET

COMMAND_EXT_SET = {".py", ".sh"}
SKIP_DIRS_FOR_LIST = {"web-tools", "gui-tools", "lib", "data", "local", "__pycache__"}


def get_external_src_dirs() -> List[str]:
    """返回已登记且仍然存在的外部工具源码目录列表 (读取 ~/.duck-rush/duck.json)。"""
    return InstallMeta.load().get_external_src_dirs()


def get_command_list(extra_roots: Optional[List[str]] = None) -> list:
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
    commands = get_command_list(get_external_src_dirs())
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

def install_func(args):
    install_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "install.py")
    install_script = os.path.normpath(install_script)
    os.system("%s %s" % (sys.executable, install_script))

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

def help_func(args):
    PARSER.print_help()

def default_func(args):
    action = args.action
    log_debug(args)
    commands = get_command_list(get_external_src_dirs())
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

    choice = input("please choose:")




ACTION_FUNC_DICT = {
    "list": list_command_func,
    "install": install_func,
    "upgrade": upgrade_func,
    "add-src-dir": add_src_dir_func,
    "dir": dir_func,
    "help": help_func,
}

ACTION_DESC = {
    "list": "列出所有已注册命令 (支持 -s/--short 只打印命令名称)",
    "install": "安装全部工具: 装依赖 -> 安装 duck_utils -> 生成命令包装脚本 -> 生成命令简介缓存",
    "upgrade": "拉取最新代码 (git pull) 并重新安装",
    "add-src-dir": "登记外部工具源码目录, 更新 duck.json 并重新生成脚本链接",
    "dir": "打印 duck-rush 项目根目录的绝对路径",
    "help": "显示本帮助信息",
}

EPILOG = (
    "可用操作 (action):\n"
    + "\n".join("  %-12s %s" % (name, ACTION_DESC.get(name, "")) for name in ACTION_FUNC_DICT)
    + "\n\n示例:\n"
    + "  duck list                      列出所有命令\n"
    + "  duck list -s                   只打印命令名称\n"
    + "  duck <命令>                    执行某个命令 (如: duck duck-json -h)\n"
    + "  duck dir                       打印项目根目录\n"
    + "  duck add-src-dir ~/my-tools   登记外部工具源码目录并生成脚本链接\n"
)

PARSER = argparse.ArgumentParser(
    description = "duck-rush 工具集入口",
    epilog = EPILOG,
    formatter_class = argparse.RawDescriptionHelpFormatter,
)
PARSER.add_argument("action", nargs = "?", help = "操作 (list/install/upgrade/dir/help)", default = "help")
PARSER.add_argument("args", nargs = "*", help = "参数")
PARSER.add_argument("-s", "--short", action = "store_true", help = "list 模式: 只打印命令名称, 不打印简介")

def main():
    args   = PARSER.parse_args()
    func = ACTION_FUNC_DICT.get(args.action, default_func)
    func(args)

if __name__ == '__main__':
    main()