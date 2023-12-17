#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/02/23 22:09:31
# @modified 2021/10/02 15:10:44
import os
import time
import sys
import platform
from termcolor import colored


MUSIC_EXT_CONFIG = "mp3|m4a|midi|wav|m3u8"
DOC_EXT_CONFIG   = "pdf|doc|docx|xls|xlsx|html|md|xmind|txt|key|numbers|csv"
VIDEO_EXT_CONFIG = "mp4|mkv|avi|rmvb|flv"
IMAGE_EXT_CONFIG = "jpg|jpeg|gif|jfif|ico|cur|png|webp|bmp|svg"
ARCHIVE_EXT_CONFIG = "zip|rar|gz|apk|dmg|pkg|exe|msi|iso|ipk|img|sis|jar|7z"
CODE_EXT_CONFIG = "h|c|cpp|hpp|java|py|js|html|json"

def convert_config_to_set(text):
    result = set()
    for item in text.split("|"):
        if item == "":
            continue
        if item[0] != ".":
            item = "." + item
        result.add(item)
    return result


MUSIC_EXT_SET = convert_config_to_set(MUSIC_EXT_CONFIG)
DOC_EXT_SET   = convert_config_to_set(DOC_EXT_CONFIG)
VIDEO_EXT_SET = convert_config_to_set(VIDEO_EXT_CONFIG)
IMAGE_EXT_SET = convert_config_to_set(IMAGE_EXT_CONFIG)
ARCHIVE_EXT_SET = convert_config_to_set(ARCHIVE_EXT_CONFIG)

def green_text(text):
    return colored(text, "green")

# device
def is_mac():
    return platform.system() == "Darwin"

def is_windows():
    return os.name == "nt"

def makedirs(dirname):
    '''检查并创建目录(如果不存在不报错)'''
    if not os.path.exists(dirname):
        os.makedirs(dirname)
        return True
    return False

def get_mac_birth_year(fpath):
    stat = os.stat(fpath)
    st   = time.localtime(stat.st_birthtime)
    return time.strftime("%Y", st)

def get_win_birth_year(fpath):
    stat = os.stat(fpath)
    st   = time.localtime(stat.st_ctime)
    return time.strftime("%Y", st)

def get_birth_year(fpath):
    if is_mac():
        return get_mac_birth_year(fpath)
    return get_win_birth_year(fpath)

def is_hidden_file(fname):
    # Unix/Linux hidden files
    if fname[0] == '.':
        return True
    # Mac OS hidden file
    if fname == '.DS_Store':
        return True
    return False

def check_file_by_ext(fname, ext_set):
    name, ext = os.path.splitext(fname)
    return ext.lower() in ext_set

def get_music_dir():
    # Mac和Win都是Music
    return os.path.join(os.environ['HOME'], "Music")

def get_document_dir():
    return os.path.join(os.environ['HOME'], "Documents")

def get_image_dir():
    return os.path.join(os.environ['HOME'], "Pictures")

def get_video_dir():
    if is_mac():
        return os.path.join(os.environ['HOME'], "Movies")
    return os.path.join(os.environ['HOME'], "Videos")

def get_download_dir():
    return os.path.join(os.environ['HOME'], 'Downloads')

def get_archive_dir():
    download_dir = get_download_dir()
    return os.path.join(download_dir, "Archives")

class DocumentClassifier:

    def check(self, fpath):
        return check_file_by_ext(fpath, DOC_EXT_SET)

    def get_target_path(self, fpath):
        fname = os.path.basename(fpath)
        return os.path.join(get_document_dir(), get_birth_year(fpath), fname)

class MusicClassifier:

    def check(self, fpath):
        return check_file_by_ext(fpath, MUSIC_EXT_SET)

    def get_target_path(self, fpath):
        fname = os.path.basename(fpath)
        return os.path.join(get_music_dir(), get_birth_year(fpath), fname)

class ImageClassifier:

    def check(self, fpath):
        return check_file_by_ext(fpath, IMAGE_EXT_SET)

    def get_target_path(self, fpath):
        fname = os.path.basename(fpath)
        return os.path.join(get_image_dir(), get_birth_year(fpath), fname)

class VideoClassifier:

    def check(self, fpath):
        return check_file_by_ext(fpath, VIDEO_EXT_SET)

    def get_target_path(self, fpath):
        fname = os.path.basename(fpath)
        return os.path.join(get_video_dir(), get_birth_year(fpath), fname)

class ArchiveClassifier:

    def check(self, fpath):
        return check_file_by_ext(fpath, ARCHIVE_EXT_SET)

    def get_target_path(self, fpath):
        fname = os.path.basename(fpath)
        return os.path.join(get_archive_dir(), get_birth_year(fpath), fname)

CLASSIFIER_LIST = [
    DocumentClassifier(),
    MusicClassifier(),
    ImageClassifier(),
    VideoClassifier(),
    ArchiveClassifier()
]

def get_target_path(fpath):
    for classifier in CLASSIFIER_LIST:
        if classifier.check(fpath):
            return classifier.get_target_path(fpath)


def classify0(dirname = '.', confirmed = False):
    found = False
    count = 0
    for fname in os.listdir(dirname):
        fpath = os.path.join(dirname, fname)

        if is_hidden_file(fname):
            continue

        if not os.path.isfile(fpath):
            continue

        target_path = get_target_path(fpath)
        if target_path is None:
            continue

        if not confirmed:
            count += 1
            found = True
            print(u"[%03d] 原路径: %s" % (count, fname))
            print(u"      新路径: {target_path}\n".format(target_path = target_path))
        else:
            target_dirname = os.path.dirname(target_path)
            makedirs(target_dirname)
            os.rename(fpath, target_path)
    return found

def classify(dirname = '.', confirmed = False):
    found = classify0(dirname, False)
    if not found:
        print("没有需要移动的文件")
        return
    user_input = input(u"\n确定移动文件吗?(y/n):")
    if user_input == "y":
        classify0(dirname, True)


if __name__ == '__main__':
    classify()