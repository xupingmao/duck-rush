# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/04/24 17:14:12
# @modified 2021/04/25 11:11:04
# @filename install-sublime-plugin.py
import os
import platform
import shutil

def get_os_user():
    return os.environ["USER"]


class InstallerBase:

    os_type = "unknown"

    def before_install(self):
        print("开始安装，检测到当前系统为:%s" % self.os_type)

    def get_os_user(self):
        return get_os_user()

    def get_plugin_path(self, fpath):
        user_name = self.get_os_user()
        return "/Users/%s/Library/Application Support/Sublime Text 3/Packages/User/%s" % (user_name, fpath)

    def do_install(self, new_plugin_file):
        if not os.path.exists(new_plugin_file):
            raise Exception("file not exist: %s" % new_plugin_file)
        # copy file
        basename = os.path.basename(new_plugin_file)
        old_plugin_file = self.get_plugin_path(basename)

        if os.path.exists(old_plugin_file):
            # do backup
            shutil.copyfile(old_plugin_file, old_plugin_file + ".bak")

        shutil.copyfile(new_plugin_file, old_plugin_file)
        print("安装插件:%s" % old_plugin_file)


    def install(self):
        self.before_install()

        this_file_path = os.path.abspath(__file__)
        dirname = os.path.dirname(this_file_path)
        cmd_file_path = os.path.join(dirname, "file_header_cmd.py")
        listener_file_path = os.path.join(dirname, "file_header_listener.py")

        self.do_install(cmd_file_path)
        self.do_install(listener_file_path)

        print("安装完成!")


class MacInstaller(InstallerBase):
    os_type = "mac"


def get_os_type():
    if platform.system() == "Darwin":
        return "mac"
    if os.name == "nt":
        return "windows"
    if os.name == "linux":
        return "linux"
    return "unknown"


def main():
    os_type = get_os_type()
    installer = None
    if os_type == "mac":
        installer = MacInstaller()

    if installer is None:
        raise Exception("unsupported os:", os_type)

    installer.install()

if __name__ == '__main__':
    main()