# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2026/03/18
# @modified 2026/03/18

import argparse
from PIL import Image
import numpy as np
from typing import Optional, List
import os


def extract_image(fpath: str, light_threshold: int = 240, dark_threshold: int = 15, margin: int = 0, remove_top: int = 0, remove_bottom: int = 0, min_border_size: int = 10) -> Optional[Image.Image]:
    """
    提取图片中央的有效区域，移除周边的空白区域
    
    Args:
        fpath: 图片文件路径
        light_threshold: 白色边框的阈值（0-255），大于此值视为白色空白
        dark_threshold: 黑色边框的阈值（0-255），小于此值视为黑色空白
        margin: 保留的边缘边距
        remove_top: 移除顶部的像素数（用于移除系统状态栏）
        remove_bottom: 移除底部的像素数（用于移除操作栏）
        min_border_size: 最小边框大小（像素），大于此值才认为是边框
    """
    img = Image.open(fpath)
    
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    img_array = np.array(img)
    height, width = img.size[1], img.size[0]
    
    center_y = height // 2
    center_x = width // 2
    
    gray = np.mean(img_array, axis=2)
    
    def is_solid_row(row_idx: int) -> bool:
        row = gray[row_idx, :]
        return np.all((row > light_threshold) | (row < dark_threshold))
    
    def is_solid_col(col_idx: int) -> bool:
        col = gray[:, col_idx]
        return np.all((col > light_threshold) | (col < dark_threshold))
    
    top = center_y
    solid_rows = []
    for y in range(center_y, -1, -1):
        if is_solid_row(y):
            solid_rows.append(y)
            if len(solid_rows) >= min_border_size:
                break
        else:
            solid_rows = []
            top = y
    
    bottom = center_y
    solid_rows = []
    for y in range(center_y, height):
        if is_solid_row(y):
            solid_rows.append(y)
            if len(solid_rows) >= min_border_size:
                break
        else:
            solid_rows = []
            bottom = y
    
    left = center_x
    solid_cols = []
    for x in range(center_x, -1, -1):
        if is_solid_col(x):
            solid_cols.append(x)
            if len(solid_cols) >= min_border_size:
                break
        else:
            solid_cols = []
            left = x
    
    right = center_x
    solid_cols = []
    for x in range(center_x, width):
        if is_solid_col(x):
            solid_cols.append(x)
            if len(solid_cols) >= min_border_size:
                break
        else:
            solid_cols = []
            right = x

    if top >= bottom or left >= right:
        print("警告：移除系统栏后无效区域，返回原图")
        return img
    
    if top == 0 and bottom + 1 == height and left == 0 and right + 1 == width:
        print("未检测到边框，返回原图")
        return img
    
    cropped = img.crop((left, top, right, bottom))
    
    basename, ext = fpath.rsplit('.', 1)
    outpath = f"{basename}_extracted.{ext}"
    cropped.save(outpath)
    
    print(f"原图尺寸: {img.size}")
    print(f"裁剪区域: ({left}, {top}, {right}, {bottom})")
    print(f"裁剪后尺寸: {cropped.size}")
    print(f"保存到: {outpath}")
    
    return cropped


def get_image_files(directory: str) -> List[str]:
    """
    获取目录中的所有图片文件
    
    Args:
        directory: 目录路径
    
    Returns:
        图片文件路径列表
    """
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
    image_files = []
    
    for filename in os.listdir(directory):
        if os.path.isfile(os.path.join(directory, filename)):
            ext = os.path.splitext(filename)[1].lower()
            if ext in image_extensions:
                image_files.append(os.path.join(directory, filename))
    
    return sorted(image_files)


def main() -> None:
    parser = argparse.ArgumentParser("图片提取工具")
    parser.add_argument("fpath", nargs='?', default=None, help="图片文件路径，为空时遍历当前目录的所有图片")
    parser.add_argument("--light-threshold", type=int, default=240, 
                       help="白色边框阈值（0-255），默认240")
    parser.add_argument("--dark-threshold", type=int, default=15,
                       help="黑色边框阈值（0-255），默认15")
    parser.add_argument("--margin", type=int, default=0,
                       help="保留的边缘边距，默认0")
    parser.add_argument("--remove-top", type=int, default=0,
                       help="移除顶部的像素数（用于移除系统状态栏），默认0")
    parser.add_argument("--remove-bottom", type=int, default=0,
                       help="移除底部的像素数（用于移除操作栏），默认0")
    parser.add_argument("--min-border-size", type=int, default=5,
                       help="最小边框大小（像素），大于此值才认为是边框，默认5")
    args = parser.parse_args()
    
    if args.fpath is None:
        current_dir = os.getcwd()
        print(f"未指定图片路径，遍历当前目录: {current_dir}")
        image_files = get_image_files(current_dir)
        
        if not image_files:
            print("当前目录没有找到图片文件")
            return
        
        print(f"找到 {len(image_files)} 个图片文件")
        for i, fpath in enumerate(image_files, 1):
            print(f"\n[{i}/{len(image_files)}] 处理: {os.path.basename(fpath)}")
            extract_image(fpath, args.light_threshold, args.dark_threshold, args.margin, args.remove_top, args.remove_bottom, args.min_border_size)
    else:
        extract_image(args.fpath, args.light_threshold, args.dark_threshold, args.margin, args.remove_top, args.remove_bottom, args.min_border_size)


if __name__ == '__main__':
    main()
