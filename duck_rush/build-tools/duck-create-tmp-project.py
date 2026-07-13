# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/07/13
# @description 创建临时项目目录（data/project/日期_项目名），并开启一个位于该目录的 shell

import os
import sys
import argparse
import time
import typing
import subprocess


def get_project_root() -> str:
    """获取 duck_rush 项目的根目录"""
    # 当前文件位于 duck_rush/<category>/<name>.py
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def build_project_name(name: str) -> str:
    """根据日期和可选的项目名生成目录名，例如 20260713_测试"""
    date_str = time.strftime("%Y%m%d", time.localtime())
    if name:
        return "%s_%s" % (date_str, name)
    return date_str


def create_tmp_project(name: str = "") -> str:
    """创建临时项目目录

    @param {str} name 项目名称（可选）
    @return {str} 创建的项目目录绝对路径
    """
    base_dir = os.path.join(get_project_root(), "data", "project")
    os.makedirs(base_dir, exist_ok=True)

    project_name = build_project_name(name)
    project_dir = os.path.join(base_dir, project_name)

    # 避免覆盖已存在的目录，但允许复用
    if os.path.exists(project_dir):
        print("目录已存在: %s" % project_dir)
    else:
        os.makedirs(project_dir)
        print("已创建目录: %s" % project_dir)

    # 默认创建 input.txt 和 main.py
    input_path = os.path.join(project_dir, "input.txt")
    main_path = os.path.join(project_dir, "main.py")

    if not os.path.exists(input_path):
        with open(input_path, "w", encoding="utf-8") as fp:
            fp.write("")

    if not os.path.exists(main_path):
        main_template = (
            "# -*- coding:utf-8 -*-\n"
            "def main():\n"
            "    pass\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        with open(main_path, "w", encoding="utf-8") as fp:
            fp.write(main_template)

    return project_dir


def open_shell_here(project_dir: str) -> None:
    """切换到项目目录并开启一个新的交互式 shell 子进程"""
    os.chdir(project_dir)
    # 优先使用当前交互 shell，否则退回到常见 shell
    shell = os.environ.get("SHELL") or os.environ.get("COMSPEC") or "bash"
    print("已切换工作目录到: %s" % project_dir)
    print("正在打开新的 shell（输入 exit 退出）...")
    if os.name == "posix":
        subprocess.call([shell, "-l"])
    else:
        subprocess.call(shell)


def main():
    parser = argparse.ArgumentParser(description = "创建临时项目目录（data/project/日期_项目名）并打开该目录下的 shell")
    parser.add_argument("--name", default = "", help = "项目名称，可省略；省略时目录名为纯日期")
    args = parser.parse_args()

    project_dir = create_tmp_project(args.name)
    open_shell_here(project_dir)


if __name__ == "__main__":
    main()
