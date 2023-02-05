# -*- coding:utf-8 -*-
"""
@Author       : xupingmao
@email        : 578749341@qq.com
@Date         : 2023-02-05 14:03:53
@LastEditors  : xupingmao
@LastEditTime : 2023-02-05 14:10:02
@FilePath     : /xnoted:/projects/duck_rush/src/os/detect-os.py
@Description  : 描述
"""

import os
import sys
import platform

# 参考文档： https://blog.csdn.net/KnownAll/article/details/81560050
# os.name 用于判断模块是否可用，只注册了三个值 posix/nt/java
print("os.name: %s" % os.name)
# sys.platform 依赖在构建配置时指定的编译器定义
print("sys.platform: %s" % sys.platform)
# platform.system() 会返回更详细的系统信息，比如 Linux/Windows/Darwin
print("platform.system(): %s" % platform.system())
