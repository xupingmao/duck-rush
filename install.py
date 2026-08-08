#!/usr/bin/env python
# encoding=utf-8
"""
duck-rush 安装工具

默认执行完整安装: 创建虚拟环境、安装依赖、生成全部命令的包装脚本等。
也可只安装指定命令(仅生成其包装脚本, 跳过虚拟环境/依赖等重步骤):

  python install.py                完整安装
  python install.py duck-cat       仅生成 duck-cat 的包装脚本
  python install.py duck-cat duck-json   同时生成多个指定命令
  python install.py --list         列出所有可安装的命令
  python install.py --duck-utils    仅安装 duck_utils 工具包(跳过完整安装)
  python install.py duck_utils      同上, 仅安装 duck_utils 工具包的另一种写法
"""

import os
import sys
import argparse
import platform
import shutil
import json
import subprocess
from typing import List, Optional, Set, Set

# 确保脚本所在目录 (仓库根) 位于 sys.path 最前。这样即使 duck_utils 尚未安装到
# 虚拟环境, install.py 也能从本地仓库导入 duck_utils 包 —— install.py 本身只依赖
# 本地源码, 不依赖 venv 内已安装的 duck_utils。其它命令可假定 duck_utils 已安装最新版,
# 无需做此处理。
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from duck_utils.duck_meta import InstallMeta


def run_cmd(args, cwd: Optional[str] = None):
    """以参数列表形式执行命令，避免 os.system 在 Windows 下因首尾引号被 cmd 吞掉而导致路径解析失败的问题。

    cwd 不传时继承父进程工作目录；传入则在该目录下执行。
    """
    return subprocess.run(args, shell=False, cwd=cwd).returncode


# pip 镜像源列表（官方源用空字符串占位）。安装失败时会依次回退尝试，
# 任一源成功即返回。macOS 等网络环境下官方源(pypi.org)经常超时，
# 依次尝试国内镜像可显著提升安装成功率。
_PIP_INDEX_URLS = [
    "",  # 官方源（不设 -i）
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
    "https://pypi.mirrors.ustc.edu.cn/simple",
    "https://mirrors.cloud.tencent.com/pypi/simple",
    "https://repo.huaweicloud.com/repository/pypi/simple",
]


def pip_install(python: str, pip_args: list) -> int:
    """使用 pip 安装，依次尝试多个镜像源，任一成功即返回。

    pip_args: 除 `python -m pip install` 之外的参数列表，
              例如 ["textual"] 或 ["-r", "requirements.txt"]。
    返回最终退出码（0 表示成功）。
    """
    for index_url in _PIP_INDEX_URLS:
        label = index_url or "官方源(pypi.org)"
        args = [
            python, "-m", "pip", "install",
            "--disable-pip-version-check",
            "--timeout", "60",
            "--retries", "5",
        ]
        if index_url:
            args += ["-i", index_url]
        args += pip_args
        log_info("尝试 pip 源安装: %s", label)
        rc = subprocess.run(args, shell=False).returncode
        if rc == 0:
            log_info("pip 安装成功（源: %s）", label)
            return 0
        log_info("pip 源失败，尝试下一个: %s", label)
    sys.stderr.write(
        "所有 pip 源均安装失败，请检查网络或手动安装: %s\n"
        % " ".join(pip_args)
    )
    return 1

try:
    from termcolor import colored
except Exception:
    # fallback：termcolor 缺失时（极少见）退化为无颜色输出。
    # termcolor.colored 的签名带有大量 Literal 字面量约束，fallback
    # 无法、也无需与之完全一致，故忽略条件分支签名一致性检查。
    def colored(msg: str, color: str) -> str:  # type: ignore[misc]
        return msg

def get_user_home_path():
    if os.name == "nt":
        return os.environ["USERPROFILE"]
    else:
        # linux/unix/macOS
        return os.environ["HOME"]


FILE_PATH  = os.path.abspath(__file__)
HOME_PATH  = get_user_home_path()
DIR_PATH   = os.path.dirname(FILE_PATH)
SRC_PATH   = os.path.join(DIR_PATH, "duck_rush")
LOCAL_PATH = os.path.join(DIR_PATH, "local")
VENV_DIR   = os.path.join(LOCAL_PATH, "venv")

# 用户级安装目录（跨平台统一）：~/.duck-rush
#   bin/   命令包装脚本（加入 PATH）
#   data/  命令运行时数据存储（data/{cmd} 每个命令一个子目录）
#   duck.json  安装元数据
DUCK_RUSH_HOME = os.path.join(HOME_PATH, ".duck-rush")
BIN_DIR   = os.path.join(DUCK_RUSH_HOME, "bin")
DATA_DIR  = os.path.join(DUCK_RUSH_HOME, "data")


def get_venv_python() -> str:
    """返回虚拟环境中的Python可执行文件路径"""
    if os.name == "nt":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def ensure_venv() -> str:
    """确保虚拟环境存在，返回虚拟环境中的python路径。

    所有依赖与模块都安装进该虚拟环境，生成的命令包装脚本也指向它，
    从而避免污染系统Python环境。
    """
    venv_python = get_venv_python()
    if os.path.exists(venv_python):
        print("虚拟环境已存在: %s" % VENV_DIR)
        return venv_python

    print("创建Python虚拟环境: %s" % VENV_DIR)
    makedirs(LOCAL_PATH)
    rc = run_cmd([sys.executable, "-m", "venv", VENV_DIR])
    if rc != 0 or not os.path.exists(venv_python):
        sys.stderr.write("创建虚拟环境失败，请确认当前Python支持 venv 模块\n")
        sys.exit(1)
    return venv_python


class InstallConfig:
    code_ext_set = set([".py", ".sh"])
    
    # 跳过的文件
    skip_file_set = set(["__init__.py"])
    
    # 非代码文件
    not_code_file_set = set([".md", ".txt", ".html"])

    @classmethod
    def is_skip_file(cls, fname=""):
        if fname in cls.skip_file_set:
            return True
        if fname.startswith("test_"):
            # 跳过测试文件, 不生成命令包装
            return True
        if fname.endswith("_util.py"):
            # 跳过 *_util.py 工具类
            return True
        return False


def log_info(fmt, *args):
    print(fmt % args)

def find_bash_profile_path():
    bash_rc = os.path.join(HOME_PATH, ".bashrc")
    if os.path.exists(bash_rc):
        return bash_rc

    bash_profile = os.path.join(HOME_PATH, ".bash_profile")
    if os.path.exists(bash_profile):
        return bash_profile

    return bash_rc

def load_bash_profile():
    fpath = find_bash_profile_path()
    if not os.path.exists(fpath):
        return ""
    with open(fpath) as fp:
        return fp.read()

def append_to_bash_profile(cmd):
    fpath = find_bash_profile_path()
    if not os.path.exists(fpath):
        # 文件不存在则先创建，避免首次安装（常见于全新环境）写入失败
        open(fpath, "w").close()
    bash_profile_text = load_bash_profile()

    if cmd in bash_profile_text:
        return

    with open(fpath, "a+") as fp:
        fp.write("\n")
        fp.write(cmd)

def add_shell_path(fpath):
    fpath = os.path.abspath(fpath)
    os.system("chmod -R +x %s" % fpath)

    cmd = "export PATH=$PATH:%s" % fpath
    append_to_bash_profile(cmd)

def makedirs(dirname):
    '''检查并创建目录(如果不存在不报错)'''
    if not os.path.exists(dirname):
        os.makedirs(dirname)
        return True
    return False


def get_external_roots() -> List[str]:
    """读取已登记的外部工具源码目录(不存在时返回空列表)。"""
    try:
        return InstallMeta.load().get_external_src_dirs()
    except Exception:
        return []


def _resolve_python() -> str:
    """解析用于包装脚本的 python 路径: 优先已安装的 venv python, 否则回退当前 python。"""
    try:
        meta = InstallMeta.load()
        if getattr(meta, "python", None) and os.path.exists(meta.python):
            return meta.python
    except Exception:
        pass
    return sys.executable


def collect_commands(extra_roots: Optional[List[str]] = None):
    '''收集所有命令并生成命令列表(含外部源码目录)。'''
    commands = []
    index = 0

    roots = [SRC_PATH] + (extra_roots or [])
    for src_root in roots:
        if not os.path.isdir(src_root):
            continue
        for root, dirs, files in os.walk(src_root):
            for fname in files:
                if InstallConfig.is_skip_file(fname):
                    continue

                name, ext = os.path.splitext(fname)
                if ext not in InstallConfig.code_ext_set:
                    continue

                fpath = os.path.abspath(os.path.join(root, fname))

                # 计算相对路径，用于分类
                rel_path = os.path.relpath(root, src_root)
                category = rel_path if rel_path != '.' else 'root'

                command = {
                    'id': index + 1,
                    'name': name,
                    'path': fpath,
                    'category': category,
                    'extension': ext
                }
                commands.append(command)
                index += 1

    return commands


def save_commands(commands):
    '''保存命令列表到data/commands.local.json'''
    data_dir = os.path.join(DIR_PATH, 'data')
    makedirs(data_dir)
    
    output_file = os.path.join(data_dir, 'commands.local.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(commands, f, ensure_ascii=False, indent=2)
    
    print(f"命令列表已保存到: {output_file}")
    print(f"共收集到 {len(commands)} 个命令")

def generate_command_desc(python: str, extra_roots: Optional[List[str]] = None) -> None:
    """安装时生成命令简介缓存 (data/install/command_desc.jsonl)。

    直接执行每个命令的 -h, 取首行非空内容作为简介; 超时(3秒)或失败则忽略。
    子进程强制 UTF-8 输出, 避免 Windows 下 GBK 管道导致的中文乱码。
    extra_roots: 外部工具源码目录, 用于把外部命令也纳入简介缓存。
    """
    import subprocess as _sp

    commands = collect_commands(extra_roots)
    if not commands:
        return

    cache_dir = os.path.join(DIR_PATH, "data", "install")
    makedirs(cache_dir)
    cache_file = os.path.join(cache_dir, "command_desc.jsonl")

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["LC_ALL"] = "C.UTF-8"
    env["LANG"] = "C.UTF-8"

    total = len(commands)
    with open(cache_file, "w", encoding="utf-8") as fp:
        for index, cmd in enumerate(commands):
            name = cmd["name"]
            ext = cmd["extension"]
            fpath = cmd["path"]
            if ext not in (".py", ".sh"):
                continue
            log_info("[%03d/%03d] 生成命令简介: %s", index + 1, total, name)
            desc = ""
            try:
                cmdline = [python, fpath, "-h"] if ext == ".py" else ["bash", fpath, "-h"]
                proc = _sp.run(
                    cmdline,
                    stdout=_sp.PIPE,
                    stderr=_sp.PIPE,
                    env=env,
                    timeout=3,
                )
                out = proc.stdout.decode("utf-8", errors="replace")
                for line in out.splitlines():
                    line = line.strip()
                    if line:
                        desc = line
                        break
            except Exception:
                desc = ""
            fp.write(json.dumps({"name": name, "desc": desc}, ensure_ascii=False) + "\n")
    print("命令简介缓存已生成: %s" % cache_file)

def check_environment():
    if os.name == "nt":
        # windows
        print("")
        print("检测到Windows环境")
        print("如果Bash Shell乱码，请依次执行下面配置:")
        print("1. 鼠标右键，选择Options")
        print("2. 选择左侧的Text")
        print("3. 找到Locale和Caracter set，将编码设置成GBK")
        print("")
        return "nt"
    else:
        print("检测到Unix/Linux环境")
        return "unix"

def is_script_file(fpath):
    name, ext = os.path.splitext(fpath)
    return ext.lower() in InstallConfig.code_ext_set

class WindowsInstaller:

    # 末尾的 echo( 输出一个换行, 避免命令输出未以换行结束时与 shell 的 prompt 混在同一行
    BAT_SCRIPT_TEMPLATE = "\r\n@echo off\r\nset DUCK_RUSH_DIR={duck_rush_dir}\r\n\"{python}\" \"{fpath}\" %*\r\necho(\r\n"
    
    NON_CODE_EXT_SET = InstallConfig.not_code_file_set


    def __init__(self, dirname, python):
        self.dirname = dirname
        self.python = python
        self.debug = False
        self.count = 0
        self.expected_names = set()

    def is_script_file(self, fpath):
        name, ext = os.path.splitext(fpath)
        return ext.lower() not in self.NON_CODE_EXT_SET

    def create_file(self, fpath):
        if not self.is_script_file(fpath):
            return

        fname = os.path.basename(fpath)
        fname_base, ext = os.path.splitext(fname)

        if ext != ".py":
            return
        
        # 只支持Python
        self.expected_names.add(fname_base + ".bat")
        content = self.BAT_SCRIPT_TEMPLATE.format(python = self.python, fpath = fpath.replace("\\", "\\\\"), duck_rush_dir=DIR_PATH)
        bat_path = os.path.join(self.dirname, fname_base + ".bat")

        # 检查文件是否存在且内容一致
        if os.path.exists(bat_path):
            # newline="" 关闭文本模式的换行符转换；比较时再忽略 \r 差异，
            # 否则 Windows 上写入会把 \n 转成 \r\n（旧文件甚至变成 \r\r\n），
            # 读回又被规整，导致每次比较都不等、脚本被反复更新。
            with open(bat_path, newline="") as fp:
                old_content = fp.read()
            if old_content.replace("\r", "") == content.replace("\r", ""):
                self.count += 1
                print("[%03d] 跳过(无变化): %s" % (self.count, bat_path))
                return

        self.count += 1
        print("[%03d] 更新脚本: %s" % (self.count, bat_path))
        if self.debug:
            print(content)
            print("")
            return

        with open(bat_path, "w", newline="") as fp:
            fp.write(content)


    def create_bat_files(self, roots: Optional[List[str]] = None, filter_names: Optional[Set[str]] = None):
        for src_root in (roots or [SRC_PATH]):
            if not os.path.isdir(src_root):
                continue
            for root, dirs, files in os.walk(src_root):
                for fname in files:
                    if InstallConfig.is_skip_file(fname):
                        continue
                    if filter_names is not None and os.path.splitext(fname)[0] not in filter_names:
                        continue
                    fpath = os.path.join(root, fname)
                    fpath = os.path.abspath(fpath)

                    self.create_file(fpath)

    def remove_stale_files(self):
        if not os.path.exists(self.dirname):
            return
        for fname in os.listdir(self.dirname):
            if fname in self.expected_names:
                continue
            fpath = os.path.join(self.dirname, fname)
            if os.path.isfile(fpath) and fname.endswith(".bat"):
                os.remove(fpath)
                print("删除过期脚本: %s" % fpath)

    def install(self, extra_roots: Optional[List[str]] = None, filter_names: Optional[Set[str]] = None):
        if not os.path.exists(self.dirname):
            os.makedirs(self.dirname)

        self.create_bat_files([SRC_PATH] + (extra_roots or []), filter_names=filter_names)
        # 仅安装指定命令时不清理其它已存在的脚本, 避免误删
        if filter_names is None:
            self.remove_stale_files()

def _norm_path(s: str) -> str:
    s = s.replace("\\", "/")
    while "//" in s:
        s = s.replace("//", "/")
    return s.rstrip("/").lower()


def _collapse_slashes(s: str) -> str:
    """把路径里重复的反斜杠折叠成单个（修复旧逻辑用 repr 写入导致的 \\\\ 翻倍）。"""
    while "\\\\" in s:
        s = s.replace("\\\\", "\\")
    return s


def _ps_quote(s: str) -> str:
    """为 PowerShell 单引号字符串安全地包裹并转义（不使用 repr，避免反斜杠翻倍）。"""
    return "'" + s.replace("'", "''") + "'"


def install_for_windows(python, extra_roots: Optional[List[str]] = None, filter_names: Optional[Set[str]] = None):
    print("准备安装duck_rush (windows平台) ...")
    makedirs(DUCK_RUSH_HOME)
    makedirs(BIN_DIR)
    makedirs(DATA_DIR)

    installer = WindowsInstaller(BIN_DIR, python)
    installer.install(extra_roots, filter_names=filter_names)

    add_path_windows(BIN_DIR)

    print("")
    print("脚本安装完成: %s" % BIN_DIR)


def _set_user_path(new: str) -> bool:
    """把 new 写入 Windows 用户级 PATH，成功返回 True。"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "[Environment]::SetEnvironmentVariable('PATH', %s, 'User')" % _ps_quote(new)],
            check=True,
        )
        return True
    except Exception:
        return False


def add_path_windows(bin_dir):
    """把 bin_dir 加入 Windows 用户级 PATH（通过 powershell 修改用户环境变量）。

    已存在则跳过新增，但**始终把 PATH 中已被旧逻辑污染（反斜杠翻倍）的条目折叠回
    单个反斜杠并去重后写回**，从而统一修复现有 PATH 里的 \\\\ 问题。
    修改需重开终端/新窗口才生效。
    """
    import termcolor
    bin_dir = os.path.abspath(bin_dir)
    try:
        old = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "[Environment]::GetEnvironmentVariable('PATH','User')"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8", "replace").strip()
    except Exception:
        old = os.environ.get("PATH", "")
    paths = [p for p in old.split(";") if p]
    # 旧逻辑用 repr() 把反斜杠翻倍（\\ -> \\\\），且去重比较时不折叠重复斜杠，
    # 导致重复安装时条目被反复追加、反斜杠越翻倍越多。这里先折叠每个条目的重复
    # 反斜杠并去重，得到规范化后的条目列表。
    norm_existing: List[str] = []
    for p in paths:
        fixed = _collapse_slashes(p)
        if _norm_path(fixed) not in [_norm_path(x) for x in norm_existing]:
            norm_existing.append(fixed)

    already = any(_norm_path(p) == _norm_path(bin_dir) for p in norm_existing)
    if not already:
        norm_existing.append(bin_dir)

    new = ";".join(norm_existing)
    if new == old:
        # 无任何变化（无损坏、无重复、已包含且格式正确），无需写入。
        if already:
            print(termcolor.colored("PATH 已包含: %s" % bin_dir, "green"))
        else:
            if _set_user_path(new):
                print(termcolor.colored(
                    "已将 %s 加入用户 PATH（重开终端或新开窗口生效）" % bin_dir, "green"))
            else:
                print(termcolor.colored(
                    "*注意* 自动加入 PATH 失败，请手动将 %s 加入用户 PATH" % bin_dir, "red"))
        return

    # new != old：要么新增了 bin_dir，要么修复了 PATH 里被污染的条目。
    if _set_user_path(new):
        if already:
            print(termcolor.colored(
                "已修复 PATH 中损坏的条目（反斜杠翻倍已折叠为单个）", "green"))
        else:
            print(termcolor.colored(
                "已将 %s 加入用户 PATH（重开终端或新开窗口生效）" % bin_dir, "green"))
    else:
        print(termcolor.colored(
            "*注意* 自动加入 PATH 失败，请手动将 %s 加入用户 PATH" % bin_dir, "red"))


def build_unix_start_code(fpath: str, ext: str, python: str) -> str:
    """构建 unix 启动脚本; 末尾的 echo 输出一个换行, 避免命令输出未以换行结束时与 shell 的 prompt 混在同一行。"""
    if ext == ".py":
        return f"{python} %r \"$@\"\necho" % fpath
    if ext == ".sh":
        return "sh %r \"$@\"\necho" % fpath
    return ""


def install_for_unix(python, extra_roots: Optional[List[str]] = None, filter_names: Optional[Set[str]] = None):
    log_info("准备安装duck_rush ... ")

    makedirs(DUCK_RUSH_HOME)
    makedirs(BIN_DIR)
    makedirs(DATA_DIR)

    # 第1步：收集所有当前应生成的脚本名
    expected_names = set()
    index = 0
    roots = [SRC_PATH] + (extra_roots or [])
    for src_root in roots:
        if not os.path.isdir(src_root):
            continue
        for root, dirs, files in os.walk(src_root):
            for fname in files:
                if not is_script_file(fname):
                    continue
                if InstallConfig.is_skip_file(fname):
                    continue
                if filter_names is not None and os.path.splitext(fname)[0] not in filter_names:
                    continue
                fpath = os.path.join(root, fname)
                fpath = os.path.abspath(fpath)
                name, ext = os.path.splitext(fname)
                expected_names.add(name)

                start_code = build_unix_start_code(fpath, ext, python)
                if not start_code:
                    continue
                start_file = os.path.abspath(os.path.join(BIN_DIR, name))

                # 检查文件是否存在且内容一致
                if os.path.exists(start_file):
                    with open(start_file) as fp:
                        old_code = fp.read()
                    if old_code == start_code:
                        log_info("[%03d]跳过(无变化)[%r]", index+1, fpath)
                        index += 1
                        continue

                makedirs(os.path.dirname(start_file))
                with open(start_file, "w") as fp:
                    fp.write(start_code)
                log_info("[%03d]更新脚本[%r]", index+1, fpath)
                index += 1

    # 第2步：删除不再需要的旧脚本(仅完整安装时清理)
    if filter_names is None and os.path.exists(BIN_DIR):
        for fname in os.listdir(BIN_DIR):
            if fname in expected_names:
                continue
            fpath = os.path.join(BIN_DIR, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)
                log_info("删除过期脚本: %r", fpath)

    # 加入 PATH（写入 ~/.bashrc 等，并赋予可执行权限）
    add_shell_path(BIN_DIR)


def load_meta() -> "InstallMeta":
    """读取已存在的安装元数据 ~/.duck-rush/duck.json。"""
    return InstallMeta.load()


def write_metadata(venv_python):
    """写入安装元数据 ~/.duck-rush/duck.json，保留已登记的外部源码目录。"""
    makedirs(DUCK_RUSH_HOME)
    meta = InstallMeta.load()
    meta.version = "1.0"
    meta.install_dir = DUCK_RUSH_HOME
    meta.bin_dir = BIN_DIR
    meta.data_dir = DATA_DIR
    meta.python = os.path.abspath(venv_python)
    meta.src_dir = SRC_PATH
    meta.save()
    print("元数据已写入: %s" % InstallMeta.meta_path())

def install_leveldb(python):
    print("安装 duck_leveldb 模块 ...")
    pip_install(python, ["duck_leveldb"])

def install_requirements(python):
    print("安装依赖包...")
    pip_install(python, ["-r", os.path.join(DIR_PATH, "config", "requirements.txt")])
    install_leveldb(python)
    print("依赖包安装完成")

def install_duck_utils_package(python):
    """安装独立的 duck_utils 工具包到虚拟环境, 使脚本可 `import duck_utils`"""
    print("安装 duck_utils 模块 ...")
    duck_utils_dir = os.path.join(DIR_PATH, "duck_utils")
    setup_py = os.path.join(duck_utils_dir, "setup.py")
    # 必须在仓库根目录(DIR_PATH)下执行, 因为 setup.py 用 packages=["duck_utils"] 需要在
    # 根目录能找到 duck_utils/ 子目录。同时显式传入 egg_info 的 --egg-base duck_utils,
    # 把 .egg-info 固定写到 duck_utils/ 下, 而不是继承父进程 CWD(否则在 docs/ 等子目录
    # 运行 install.py 时会把 egg-info 写到那里, 且旧的清理逻辑只删 DIR_PATH 下的副本)。
    run_cmd([python, setup_py, "egg_info", "--egg-base", "duck_utils", "sdist", "install"], cwd=DIR_PATH)
    print("清理临时文件...")
    for d in ("build", "dist", "duck_utils.egg-info"):
        shutil.rmtree(os.path.join(duck_utils_dir, d), ignore_errors=True)
        shutil.rmtree(os.path.join(DIR_PATH, d), ignore_errors=True)
    print("duck_utils模块安装完成")

def do_install():
    if sys.version_info < (3,6):
        sys.stderr.write("require python >= 3.6")
        sys.exit(1)

    venv_python = ensure_venv()

    install_requirements(venv_python)
    install_duck_utils_package(venv_python)

    env = check_environment()

    # 读取已记录的外部工具源码目录 (若存在), 用于同时生成外部命令的脚本链接
    meta = load_meta()
    external_roots = meta.get_external_src_dirs()

    if env == "nt":
        install_for_windows(venv_python, external_roots)
    else:
        install_for_unix(venv_python, external_roots)

    # 收集并保存命令列表 (含外部源码目录)
    print("\n收集命令列表...")
    commands = collect_commands(external_roots)
    save_commands(commands)

    # 生成命令简介缓存 (供 duck list 使用, 含外部命令)
    print("\n生成命令简介缓存...")
    generate_command_desc(venv_python, external_roots)

    # 写入安装元数据 ~/.duck-rush/duck.json
    write_metadata(venv_python)

    print(colored("安装完成!", "green"))

    # 汇总信息
    print("")
    print("=" * 40)
    print("安装汇总")
    print("=" * 40)
    print("  操作系统: %s" % platform.platform())
    print("  Python版本: %s" % sys.version.split()[0])
    print("  虚拟环境: %s" % VENV_DIR)
    print("  脚本总数: %d" % len(commands))
    print("=" * 40)

def install_specific(commands: List[str]) -> None:
    """仅生成/更新指定命令的包装脚本, 跳过虚拟环境、依赖安装等重步骤。"""
    python = _resolve_python()
    makedirs(DUCK_RUSH_HOME)
    makedirs(BIN_DIR)
    makedirs(DATA_DIR)

    all_cmds = collect_commands(get_external_roots())
    matched = [c for c in all_cmds if c["name"] in set(commands)]
    found = {c["name"] for c in matched}
    for name in sorted(set(commands) - found):
        sys.stderr.write("未找到命令: %s\n" % name)
    if not matched:
        sys.stderr.write("没有匹配的已注册命令, 未生成任何包装脚本\n")
        return

    filter_names = {c["name"] for c in matched}
    if os.name == "nt":
        install_for_windows(python, get_external_roots(), filter_names=filter_names)
    else:
        install_for_unix(python, get_external_roots(), filter_names=filter_names)

    print("")
    print("已安装 %d 个指定命令的包装脚本: %s"
          % (len(matched), ", ".join(sorted(filter_names))))


def install_duck_utils_only() -> None:
    """仅安装 duck_utils 工具包到虚拟环境, 跳过依赖与命令包装脚本等重步骤。

    适用于只需更新 duck_utils (如新增了 os_util.emoji_supported 等共享能力),
    而不想重跑完整安装的场景。
    """
    venv_python = ensure_venv()
    install_duck_utils_package(venv_python)
    print(colored("duck_utils 安装完成!", "green"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="duck-rush 安装工具: 默认完整安装; 也可仅安装指定命令或仅安装 duck_utils。")
    parser.add_argument("commands", nargs="*",
                        help="仅安装指定命令(生成对应包装脚本), 跳过完整安装")
    parser.add_argument("--list", action="store_true",
                        help="列出所有可安装的命令后退出")
    parser.add_argument("--duck-utils", action="store_true", dest="duck_utils",
                        help="仅安装 duck_utils 工具包(跳过完整安装)")
    args = parser.parse_args()

    if args.list:
        for cmd in collect_commands(get_external_roots()):
            print(cmd["name"])
        return
    # 支持 `install.py duck_utils` 写法
    if "duck_utils" in args.commands:
        args.commands.remove("duck_utils")
        args.duck_utils = True
    if args.duck_utils:
        install_duck_utils_only()
        return
    if args.commands:
        install_specific(args.commands)
        return
    do_install()


if __name__ == '__main__':
    # -h/--help 不得产生副作用(不创建虚拟环境/不安装依赖), 直接打印用法后退出
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip() if __doc__ else "Usage: install.py [command ...] [--list]")
        sys.exit(0)
    main()


