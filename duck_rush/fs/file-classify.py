#!/usr/local/bin/python3
# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/02/23 22:09:31
# @modified 2021/10/02 15:10:44
import os
import time
import sys
import abc
import platform
from typing import Set, Optional, List
from termcolor import colored


MUSIC_EXT_CONFIG: str = "mp3|m4a|midi|wav|m3u8"
DOC_EXT_CONFIG: str   = "pdf|doc|docx|xls|xlsx|html|md|xmind|txt|key|numbers|csv"
VIDEO_EXT_CONFIG: str = "mp4|mkv|avi|rmvb|flv"
IMAGE_EXT_CONFIG: str = "jpg|jpeg|gif|jfif|ico|cur|png|webp|bmp|svg"
ARCHIVE_EXT_CONFIG: str = "zip|rar|gz|iso|ipk|img|sis|7z|jad"
PROGRAM_EXT_CONFIG: str = "exe|msi|dmg|pkg|apk|jar"
CODE_EXT_CONFIG: str = "h|c|cpp|hpp|java|py|js|html|json"


def convert_config_to_set(text: str) -> Set[str]:
    result: Set[str] = set()
    for item in text.split("|"):
        if item == "":
            continue
        if item[0] != ".":
            item = "." + item
        result.add(item)
    return result


MUSIC_EXT_SET: Set[str] = convert_config_to_set(MUSIC_EXT_CONFIG)
DOC_EXT_SET: Set[str]   = convert_config_to_set(DOC_EXT_CONFIG)
VIDEO_EXT_SET: Set[str] = convert_config_to_set(VIDEO_EXT_CONFIG)
IMAGE_EXT_SET: Set[str] = convert_config_to_set(IMAGE_EXT_CONFIG)
ARCHIVE_EXT_SET: Set[str] = convert_config_to_set(ARCHIVE_EXT_CONFIG)
PROGRAM_EXT_SET: Set[str] = convert_config_to_set(PROGRAM_EXT_CONFIG)


def green_text(text: str) -> str:
    return colored(text, "green")


def is_mac() -> bool:
    return platform.system() == "Darwin"


def is_windows() -> bool:
    return os.name == "nt"


def makedirs(dirname: str) -> bool:
    if not os.path.exists(dirname):
        os.makedirs(dirname)
        return True
    return False


DATE_FORMAT: str = "%Y%m%d"


def get_mac_birth_date(fpath: str) -> str:
    stat = os.stat(fpath)
    st = time.localtime(stat.st_birthtime)
    return time.strftime(DATE_FORMAT, st)


def get_win_birth_date(fpath: str) -> str:
    stat = os.stat(fpath)
    st = time.localtime(stat.st_ctime)
    return time.strftime(DATE_FORMAT, st)


def get_birth_date(fpath: str) -> str:
    if is_mac():
        return get_mac_birth_date(fpath)
    return get_win_birth_date(fpath)


def get_birth_year(fpath: str) -> str:
    return get_birth_date(fpath)[:4]


def is_hidden_file(fname: str) -> bool:
    if fname[0] == '.':
        return True
    if fname == '.DS_Store':
        return True
    return False


def check_file_by_ext(fname: str, ext_set: Set[str]) -> bool:
    name, ext = os.path.splitext(fname)
    return ext.lower() in ext_set


def get_home() -> str:
    if is_windows():
        return os.environ["USERPROFILE"]
    return os.environ["HOME"]


def get_music_dir() -> str:
    return os.path.join(get_home(), "Music")


def get_document_dir() -> str:
    return os.path.join(get_home(), "Documents")


def get_image_dir() -> str:
    return os.path.join(get_home(), "Pictures")


def get_video_dir() -> str:
    if is_mac():
        return os.path.join(get_home(), "Movies")
    return os.path.join(get_home(), "Videos")


def get_download_dir() -> str:
    return os.path.join(get_home(), 'Downloads')


def get_archive_dir() -> str:
    return os.path.join(get_download_dir(), "Archives")


def get_program_dir() -> str:
    return os.path.join(get_download_dir(), "Programs")


def has_date_prefix(name: str) -> bool:
    return len(name) > 9 and name[:8].isdigit() and name[8] == '_'


def strip_dup_date_prefix(name: str) -> str:
    if len(name) > 18 and name[:8].isdigit() and name[8] == '_' \
            and name[9:17].isdigit() and name[17] == '_':
        return name[:9] + name[18:]
    return name


def build_target_path(base_dir: str, fpath: str) -> str:
    fname = os.path.basename(fpath)
    name, ext = os.path.splitext(fname)
    name = strip_dup_date_prefix(name)
    year_dir = get_birth_year(fpath)
    if has_date_prefix(name):
        return os.path.join(base_dir, year_dir, name + ext)
    date_str = get_birth_date(fpath)
    return os.path.join(base_dir, year_dir, "%s_%s%s" % (date_str, name, ext))


class BaseClassifier(abc.ABC):

    @abc.abstractmethod
    def check(self, fpath: str) -> bool:
        pass

    @abc.abstractmethod
    def get_target_path(self, fpath: str) -> Optional[str]:
        pass


class DocumentClassifier(BaseClassifier):

    def check(self, fpath: str) -> bool:
        return check_file_by_ext(fpath, DOC_EXT_SET)

    def get_target_path(self, fpath: str) -> str:
        return build_target_path(get_document_dir(), fpath)


class MusicClassifier(BaseClassifier):

    def check(self, fpath: str) -> bool:
        return check_file_by_ext(fpath, MUSIC_EXT_SET)

    def get_target_path(self, fpath: str) -> str:
        return build_target_path(get_music_dir(), fpath)


class ImageClassifier(BaseClassifier):

    def check(self, fpath: str) -> bool:
        return check_file_by_ext(fpath, IMAGE_EXT_SET)

    def get_target_path(self, fpath: str) -> str:
        return build_target_path(get_image_dir(), fpath)


class VideoClassifier(BaseClassifier):

    def check(self, fpath: str) -> bool:
        return check_file_by_ext(fpath, VIDEO_EXT_SET)

    def get_target_path(self, fpath: str) -> str:
        return build_target_path(get_video_dir(), fpath)


class ArchiveClassifier(BaseClassifier):

    def check(self, fpath: str) -> bool:
        return check_file_by_ext(fpath, ARCHIVE_EXT_SET)

    def get_target_path(self, fpath: str) -> str:
        return build_target_path(get_archive_dir(), fpath)


class ProgramClassifier(BaseClassifier):

    def check(self, fpath: str) -> bool:
        return check_file_by_ext(fpath, PROGRAM_EXT_SET)

    def get_target_path(self, fpath: str) -> str:
        return build_target_path(get_program_dir(), fpath)


CLASSIFIER_LIST: List[BaseClassifier] = [
    DocumentClassifier(),
    MusicClassifier(),
    ImageClassifier(),
    VideoClassifier(),
    ProgramClassifier(),
    ArchiveClassifier(),
]


def get_target_path(fpath: str) -> Optional[str]:
    for classifier in CLASSIFIER_LIST:
        if classifier.check(fpath):
            return classifier.get_target_path(fpath)
    return None


def resolve_target_path(target_path: str) -> str:
    if not os.path.exists(target_path):
        return target_path
    base_dir = os.path.dirname(target_path)
    fname = os.path.basename(target_path)
    name, ext = os.path.splitext(fname)
    counter = 1
    while True:
        new_name = "%s_%d%s" % (name, counter, ext)
        new_path = os.path.join(base_dir, new_name)
        if not os.path.exists(new_path):
            return new_path
        counter += 1


def classify0(dirname: str = '.', confirmed: bool = False) -> bool:
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

        target_path = resolve_target_path(target_path)

        if not confirmed:
            count += 1
            found = True
            print(u"[%03d] 原路径: %s" % (count, fname))
            print(u"      新路径: {target_path}\n".format(target_path=target_path))
        else:
            target_dirname = os.path.dirname(target_path)
            makedirs(target_dirname)
            os.rename(fpath, target_path)
    return found


def classify(dirname: str = '.', confirmed: bool = False) -> None:
    found = classify0(dirname, False)
    if not found:
        print("没有需要移动的文件")
        return

    if confirmed:
        classify0(dirname, True)
        return

    user_input = input(u"\n确定移动文件吗?(y/n):")
    if user_input == "y":
        classify0(dirname, True)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="文件自动分类工具 - 按类型将文件移动到对应目录")
    parser.add_argument("dir", nargs="?", default=".", help="要分类的目录 (默认当前目录)")
    parser.add_argument("-y", "--yes", action="store_true", help="直接移动，不询问确认")
    args = parser.parse_args()
    classify(args.dir, confirmed=args.yes)


if __name__ == '__main__':
    main()
