# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/04/18 17:26:55
# @modified 2021/04/18 17:27:23
# @filename sublime-text-config.py


def main():
    pass

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        if __doc__ is not None:
            print(__doc__.strip())
        else:
            print("Usage: " + sys.argv[0] + " [options]")
        sys.exit(0)

    main()