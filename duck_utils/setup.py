# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2026/07/19
# 独立工具包 duck_utils, 由 install.py 单独安装到本地,
# 使各脚本可通过 `import duck_utils` 直接使用, 无需关心 duck_rush 是否安装。
import os
import setuptools

# README.md 位于仓库根目录, setup.py 在 duck_utils/ 下, 故上一级即仓库根
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_README = os.path.join(_REPO_ROOT, "README.md")
with open(_README, "r", encoding="utf-8") as fp:
    long_description = fp.read()

setuptools.setup(
    name="duck_utils",
    version="0.0.1",
    author="xupingmao",
    author_email="578749341@qq.com",
    description="duck-rush 共享工具模块(跨平台)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=["duck_utils"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
