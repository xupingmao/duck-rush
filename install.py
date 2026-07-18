#!/usr/bin/env python
# encoding=utf-8

import os
import sys
import platform
import shutil
import json
import subprocess


def run_cmd(args):
    """以参数列表形式执行命令，避免 os.system 在 Windows 下因首尾引号被 cmd 吞掉而导致路径解析失败的问题。"""
    return subprocess.run(args, shell=False).returncode

try:
    from termcolor import colored
except:
    def colored(msg, color):
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
    with open(fpath) as fp:
        return fp.read()

def append_to_bash_profile(cmd):
    fpath = find_bash_profile_path()
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


def collect_commands():
    '''收集所有命令并生成命令列表'''
    commands = []
    index = 0
    
    for root, dirs, files in os.walk(SRC_PATH):
        for fname in files:
            if InstallConfig.is_skip_file(fname):
                continue
                
            name, ext = os.path.splitext(fname)
            if ext not in InstallConfig.code_ext_set:
                continue
                
            fpath = os.path.join(root, fname)
            fpath = os.path.abspath(fpath)
            
            # 计算相对路径，用于分类
            rel_path = os.path.relpath(root, SRC_PATH)
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

    BAT_SCRIPT_TEMPLATE = "\r\n@echo off\r\nset DUCK_RUSH_DIR={duck_rush_dir}\r\n\"{python}\" \"{fpath}\" %*\r\n"
    
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
            with open(bat_path) as fp:
                old_content = fp.read()
            if old_content == content:
                self.count += 1
                print("[%03d] 跳过(无变化): %s" % (self.count, bat_path))
                return

        self.count += 1
        print("[%03d] 更新脚本: %s" % (self.count, bat_path))
        if self.debug:
            print(content)
            print("")
            return

        with open(bat_path, "w") as fp:
            fp.write(content)


    def create_bat_files(self):
        for root, dirs, files in os.walk(SRC_PATH):
            for fname in files:
                if InstallConfig.is_skip_file(fname):
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

    def install(self):
        if not os.path.exists(self.dirname):
            os.makedirs(self.dirname)

        self.create_bat_files()
        self.remove_stale_files()

def install_for_windows(python):
    import termcolor
    print("准备安装duck_rush (windows平台) ...")
    user_profile_path = os.environ["USERPROFILE"]

    duck_bin_dir = os.path.join(user_profile_path, "duck_rush")

    installer = WindowsInstaller(duck_bin_dir, python)
    installer.install()

    print("")
    print("脚本安装完成!")
    
    # 检查环境变量是否已经设置
    path_env = os.environ.get("PATH", "")
    duck_bin_dir_normalized = duck_bin_dir.replace("\\", "/")
    path_env_normalized = path_env.replace("\\", "/")
    
    if duck_bin_dir_normalized in path_env_normalized:
        # 环境变量已经设置
        msg = f"环境变量已经设置: {duck_bin_dir}"
        print(termcolor.colored(msg, "green"))
        print("无需再配置环境变量，可直接使用duck_rush工具!")
    else:
        # 环境变量未设置
        msg = f"*注意* Windows需要手动配置环境变量 {duck_bin_dir}"
        print(termcolor.colored(msg, "red"))
        print("打开SystemPropertiesAdvanced进行配置...")
        os.system("SystemPropertiesAdvanced.exe")


def install_for_unix(python):
    log_info("准备安装duck_rush ... ")

    local_bin_path = os.path.join(LOCAL_PATH, "bin")
    makedirs(local_bin_path)

    def get_start_code(fpath, ext):
        """构建启动脚本"""
        if ext == ".py":
            return f"{python} %r \"$@\"" % fpath
        if ext == ".sh":
            return "sh %r \"$@\"" % fpath
        return ""

    # 第1步：收集所有当前应生成的脚本名
    expected_names = set()
    index = 0
    for root, dirs, files in os.walk(SRC_PATH):
        for fname in files:
            if not is_script_file(fname):
                continue
            if InstallConfig.is_skip_file(fname):
                continue
            fpath = os.path.join(root, fname)
            fpath = os.path.abspath(fpath)
            name, ext = os.path.splitext(fname)
            expected_names.add(name)

            start_code = get_start_code(fpath, ext)
            start_file = os.path.join(local_bin_path, name)
            start_file = os.path.abspath(start_file)

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

    # 第2步：删除不再需要的旧脚本
    if os.path.exists(local_bin_path):
        for fname in os.listdir(local_bin_path):
            if fname in expected_names:
                continue
            fpath = os.path.join(local_bin_path, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)
                log_info("删除过期脚本: %r", fpath)

    # 本地的一些临时脚本
    makedirs(LOCAL_PATH)
    add_shell_path(LOCAL_PATH)

    # 必须在最后添加并且标记为执行文件
    add_shell_path(local_bin_path)

def install_leveldb(python):
    print("安装 duck_leveldb 模块 ...")
    run_cmd([python, "-m", "pip", "install", "duck_leveldb"])

def install_requirements(python):
    print("安装依赖包...")
    run_cmd([python, "-m", "pip", "install", "-r", os.path.join(DIR_PATH, "config", "requirements.txt")])
    install_leveldb(python)
    print("依赖包安装完成")

def install_duck_rush_package(python):
    print("安装 duck_rush 模块 ...")
    run_cmd([python, os.path.join(DIR_PATH, "setup.py"), "sdist", "install"])
    print("清理临时文件...")
    for d in ("build", "dist", "duck_rush.egg-info"):
        shutil.rmtree(os.path.join(DIR_PATH, d), ignore_errors=True)
    print("duck_rush模块安装完成")

def install_duck_utils_package(python):
    """安装独立的 duck_utils 工具包到虚拟环境, 使脚本可 `import duck_utils`"""
    print("安装 duck_utils 模块 ...")
    run_cmd([python, os.path.join(DIR_PATH, "duck_utils", "setup.py"), "sdist", "install"])
    print("清理临时文件...")
    for d in ("build", "dist", "duck_utils.egg-info"):
        shutil.rmtree(os.path.join(DIR_PATH, d), ignore_errors=True)
    print("duck_utils模块安装完成")

def do_install():
    if sys.version_info < (3,6):
        sys.stderr.write("require python >= 3.6")
        sys.exit(1)

    venv_python = ensure_venv()

    install_requirements(venv_python)
    install_duck_rush_package(venv_python)
    install_duck_utils_package(venv_python)

    env = check_environment()

    if env == "nt":
        install_for_windows(venv_python)
    else:
        install_for_unix(venv_python)
    
    # 收集并保存命令列表
    print("\n收集命令列表...")
    commands = collect_commands()
    save_commands(commands)
    
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

if __name__ == '__main__':
    do_install()


