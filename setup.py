# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/12/06 16:50:48
# @modified 2020/12/06 16:54:14

import setuptools

with open("README.md", "r", encoding="utf-8") as fp:
    long_description = fp.read()


setuptools.setup(
    name = "duck_rush",
    version = "0.0.1",
    author = "mark",
    author_email = "578749341@qq.com",
    description  = "Python函数库",
    long_description = long_description,
    long_description_content_type = "text/markdown",
    packages = setuptools.find_packages(),
    classifiers = [
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ]
)
