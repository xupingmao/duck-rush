#!/usr/bin/env python
# encoding=utf-8

import os
import sys
import shutil

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
    bash_profile = os.path.join(HOME_PATH, ".bash_profile")
    if os.path.exists(bash_profile):
        return bash_profile

    bash_rc = os.path.join(HOME_PATH, ".bashrc")
    if os.path.exists(bash_rc):
        return bash_rc
    raise Exception("bash profile not found!")

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

    cmd = "PATH=$PATH:%s" % fpath
    append_to_bash_profile(cmd)

def makedirs(dirname):
    '''检查并创建目录(如果不存在不报错)'''
    if not os.path.exists(dirname):
        os.makedirs(dirname)
        return True
    return False

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
        return "unix"

def is_script_file(fpath):
    name, ext = os.path.splitext(fpath)
    return ext.lower() in InstallConfig.code_ext_set

class WindowsInstaller:

    BAT_SCRIPT_TEMPLATE = """
@echo off
set DUCK_RUSH_DIR={duck_rush_dir}
{python} "{fpath}" %*
"""
    
    NON_CODE_EXT_SET = InstallConfig.not_code_file_set


    def __init__(self, dirname):
        self.dirname = dirname
        self.debug = False
        self.count = 0

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
        content = self.BAT_SCRIPT_TEMPLATE.format(python = sys.executable, fpath = fpath.replace("\\", "\\\\"), duck_rush_dir=DIR_PATH)
        bat_path = os.path.join(self.dirname, fname_base + ".bat")

        self.count += 1
        print("[%03d] 安装脚本: %s" % (self.count, bat_path))
        if self.debug:
            print(content)
            print("")
            return

        with open(bat_path, "w+") as fp:
            fp.write(content)


    def create_bat_files(self):
        for root, dirs, files in os.walk(SRC_PATH):
            for fname in files:
                if InstallConfig.is_skip_file(fname):
                    continue
                fpath = os.path.join(root, fname)
                fpath = os.path.abspath(fpath)

                self.create_file(fpath)

    def install(self):
        if not os.path.exists(self.dirname):
            os.makedirs(self.dirname)

        self.create_bat_files()

def install_for_windows():
    import termcolor
    print("准备安装duck_rush (windows平台) ...")
    user_profile_path = os.environ["USERPROFILE"]

    duck_bin_dir = os.path.join(user_profile_path, "duck_rush")

    installer = WindowsInstaller(duck_bin_dir)
    installer.install()

    print("")
    print("脚本安装完成!")
    msg = "*注意* Windows需要手动配置环境变量 C:\\Users\\%s\\duck_rush" % user_profile_path
    print(termcolor.colored(msg, "red"))


def install_for_unix():
    log_info("准备安装duck_rush ... ")

    def get_start_code(fpath, ext):
        """构建启动脚本"""
        if ext == ".py":
            return f"{sys.executable} %r $*" % fpath
        if ext == ".sh":
            return "sh %r $*" % fpath
        return ""

    def save_start_code(fpath, code):
        dirname = os.path.dirname(fpath)
        # log_info("%s :: %s", fpath, code)
        makedirs(dirname)
        with open(fpath, "w") as fp:
            fp.write(code)

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
            start_code = get_start_code(fpath, ext)
            start_file = os.path.join(LOCAL_PATH, "bin", name)
            start_file = os.path.abspath(start_file)
            save_start_code(start_file, start_code)
            log_info("[%03d]安装脚本[%r]", index+1, fpath)
            index += 1

    # 本地的一些临时脚本
    makedirs(LOCAL_PATH)
    add_shell_path(LOCAL_PATH)

    # 必须在最后添加并且标记为执行文件
    local_bin_path = os.path.join(LOCAL_PATH, "bin")
    makedirs(local_bin_path)
    add_shell_path(local_bin_path)

def install_requirements():
    # import pip
    print("安装依赖包...")
    os.system(f"{sys.executable} -m pip install -r config/requirements.txt")
    print("依赖包安装完成")

def install_duck_rush_package():
    print("安装 duck_rush 模块 ...")
    os.system(f"{sys.executable} setup.py sdist install")
    print("清理临时文件...")
    shutil.rmtree("./build", ignore_errors=True)
    shutil.rmtree("./dist", ignore_errors=True)
    shutil.rmtree("./duck_rush.egg-info", ignore_errors=True)
    print("duck_rush模块安装完成")

def do_install():
    if sys.version_info < (3,6):
        sys.stderr.write("require python >= 3.6")
        sys.exit(1)

    install_requirements()
    install_duck_rush_package()

    env = check_environment()

    if env == "nt":
        install_for_windows()
    else:
        install_for_unix()
    
    print(colored("安装完成!", "green"))

if __name__ == '__main__':
    do_install()


