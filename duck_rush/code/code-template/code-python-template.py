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
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        if __doc__ is not None:
            print(__doc__.strip())
        else:
            print("Usage: " + sys.argv[0] + " [options]")
        sys.exit(0)
