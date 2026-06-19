# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/11/29 13:44:18
# @modified 2021/04/18 17:41:34

from my_mod import a


"""
__init__ 模块总是最早执行，哪怕是 from mod import sub_mod 也是先执行mod.__init__

输出结果
    >>> my_mod.__init__
    >>> my_mod.a
"""

