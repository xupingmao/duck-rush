#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/11/08 23:59:12
# @modified 2020/11/09 00:17:31

from PIL import Image
import os

IMG_EXT_SET = set([
    ".png",".jpg",".gif",".jpeg"
])

def is_img_file(ext):
    return ext in IMG_EXT_SET

def try_fix_web_res(ext):
    parts = ext.split("?")
    if len(parts) > 1 and parts[0] in IMG_EXT_SET:
        return parts[0]
    else:
        return ext

def append_size(dirname):
    for fname in os.listdir(dirname):
        fpath = os.path.join(dirname, fname)
        basename, ext = os.path.splitext(fpath)
        ext = try_fix_web_res(ext)

        if not is_img_file(ext):
            continue

        img = Image.open(fpath)
        width  = img.size[0]
        height = img.size[1]

        size_suffix = "%sx%s" % (width, height)
        new_path = "%s_%s%s" % (basename, size_suffix, ext)

        if basename.endswith(size_suffix):
            print("[INFO] 已经追加了: %s" % fpath)
            continue

        os.rename(fpath, new_path)

        print("[INFO] 重命名 %s 为 %s" % (fpath, new_path))

if __name__ == '__main__':
    append_size(".")