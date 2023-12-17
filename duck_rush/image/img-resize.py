#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/11/04 00:34:00
# @modified 2020/11/13 01:14:10

from PIL import Image, ImageShow
import os
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

# matplotlib教程 https://www.runoob.com/numpy/numpy-matplotlib.html

def resize_image(fpath, scale, save = True):
    if not os.path.exists(fpath):
        print("文件不存在:", fpath)
        return

    if not os.path.isfile(fpath):
        print("非法文件类型:", fpath)
        return

    # 文档 https://www.osgeo.cn/pillow/reference/Image.html
    img = Image.open(fpath)
    width  = int(img.size[0] * scale)
    height = int(img.size[1] * scale)
    # PIL.Image.NEAREST
    # PIL.Image.BOX
    # PIL.Image.BILINEAR
    # PIL.Image.HAMMING
    # PIL.Image.BICUBIC 
    # PIL.Image.LANCZOS 
    # 默认筛选器为 PIL.Image.BICUBIC . 如果图像具有模式“1”或“P”，则始终设置为 PIL.Image.NEAREST
    img_new = img.resize((width, height), Image.NEAREST)

    basename, ext = os.path.splitext(fpath)
    outpath = "%s_%sx%s%s" % (basename, width, height, ext)

    if save:
        img_new.save(outpath)
    # ImageDraw.Draw(img_new)
    # img_new.show() 调用系统的打开图片的软件
    # ImageShow.show(img_new) 也是系统的打开图片的软件

    # im = mpimg.imread(outpath)
    # plt.imshow(im)
    # plt.imshow(img_new)
    # plt.show()


resize_image("../../data/口袋妖怪.jpg", 3.5, False)
