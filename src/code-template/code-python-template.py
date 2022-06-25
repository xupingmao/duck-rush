# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/11/21 11:25:45
# @modified 2020/11/21 11:34:51
import duck_rush as duck

HEADER = """# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/11/21 11:25:45
# @modified 2020/11/21 11:25:45
"""


def create_from_template(fpath):
    fsize = duck.get_file_size(fpath)