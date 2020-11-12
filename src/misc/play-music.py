#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/02/24 12:17:08
# @modified 2020/11/10 01:11:29
import pygame
import sys
import argparse
import os
import time
import traceback

MUSIC_FILE_EXT_TUPLE = (".mp3", ".wav")

def play_music(fpath):
    if not os.path.isfile(fpath):
        return
    if not fpath.endswith(MUSIC_FILE_EXT_TUPLE):
        return
    fname = os.path.basename(fpath)
    print("Play [%s] ..." % fname)

    # os.system("open %r" % fpath)
    # return
    
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(fpath)
        pygame.mixer.music.play(0, 0)
        # 有时候没加载完会直接退出
        time.sleep(0.1)
        while pygame.mixer.music.get_busy() == 1:
            time.sleep(1)
    except Exception:
        ex_type, ex, tb = sys.exc_info()
        exc_info = traceback.format_exc()
        print(exc_info)

def main(fpath):
    if os.path.isdir(fpath):
        for fname in os.listdir(fpath):
            play_music(os.path.join(fpath, fname))
    else:
        play_music(fpath)
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = "播放音乐工具")
    parser.add_argument("path", nargs = "?", help = "音乐文件/文件夹路径", default = ".")
    args   = parser.parse_args(sys.argv[1:])
    main(args.path)