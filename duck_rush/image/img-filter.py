# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/11/13 01:14:01
# @modified 2020/11/15 22:55:56

import argparse
from PIL import Image, ImageFilter
import numpy as np
import matplotlib.pyplot as plt

FILTER_LIST = [
    ImageFilter.BLUR, # 模糊滤镜
    ImageFilter.CONTOUR, # 铅笔轮廓滤镜
    ImageFilter.EMBOSS,  # 浮雕滤镜
    ImageFilter.EDGE_ENHANCE,  # 边缘凸显滤镜
    ImageFilter.EDGE_ENHANCE_MORE,  # 边缘凸显滤镜（加强）
    ImageFilter.FIND_EDGES,  # 只保留滤镜
    ImageFilter.SHARPEN,  # 锐化滤镜
    ImageFilter.SMOOTH ,# 平滑滤镜
    ImageFilter.SMOOTH_MORE,  # 平滑滤镜(加强)
]

class PlotViewer:

    def __init__(self, plt):
        self.plt = plt

    def show(self, title, im, index):
        plt = self.plt
        ax = plt.subplot(3,3,index)
        ax.set_title(title)
        plt.imshow(im)

def plt_show(plt, title, im, index):
    ax = plt.subplot(3,3,index)
    ax.set_title(title)
    plt.imshow(im)

def img_filter(fpath):
    # PIL的图片数组是 (R, G, B)
    im = Image.open(fpath)

    plt.figure(figsize=(12, 9))

    # 图片合并展示
    # https://www.cnblogs.com/dengfaheng/p/12720431.html

    # 设置子图标题
    # https://blog.csdn.net/a19990412/article/details/81407701

    # 221表示将画板划分为2行2列，然后取第1个区域。
    # plt.subplot(rows, cols, index)
    # plt.subplot(221)
    plt_show(plt, "Original", im, 1)

    im_2 = im.filter(ImageFilter.CONTOUR)
    plt_show(plt, "contour", im_2, 2)

    im_3 = im.filter(ImageFilter.EMBOSS)
    plt_show(plt, "emboss", im_3, 3)

    im_4 = im.filter(ImageFilter.EDGE_ENHANCE)
    plt_show(plt, "edge_enhance", im_4, 4)

    # 红色滤镜
    arr = np.array(im)
    arr[:,:,1] = 0
    arr[:,:,2] = 0
    im_5 = Image.fromarray(arr)
    plt_show(plt, "red", im_5, 5)

    # 绿色滤镜
    arr = np.array(im)
    arr[:,:,0] = 0
    arr[:,:,2] = 0
    im_6 = Image.fromarray(arr)
    plt_show(plt, "green", im_6, 6)

    # 蓝色滤镜
    arr = np.array(im)
    arr[:,:,0] = 0
    arr[:,:,1] = 0
    im_7 = Image.fromarray(arr)
    plt_show(plt, "blue", im_7, 7)


    # TODO 灰色滤镜，这里的PIL和matplotlib显示不一样
    im_8 = im.convert("L")
    plt_show(plt, "gray", im_8, 8)

    im_9 = im.convert("1")
    plt_show(plt, "1", im_9, 9)
    # 可以把表存储起来
    # plt.savefig('cifar-10.png')

    # plt.show() 只需要调用一次
    plt.show()


def main():
    parser = argparse.ArgumentParser("图片滤镜")
    parser.add_argument("fpath", help = "文件路径")
    args = parser.parse_args()
    img_filter(args.fpath)

if __name__ == '__main__':
    main()

