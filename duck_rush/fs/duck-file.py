# -*- coding: utf-8 -*-
"""duck-file — 通过检查文件内容(magic bytes)判断文件类型, 复刻 Unix file 命令。

用法:
  duck-file [-b] [-i] [-L] 文件 [文件...]

选项:
  -b, --brief     不输出文件名, 只输出类型描述
  -i, --mime      输出 MIME 类型而不是文字描述
  -L, --dereference  对符号链接解析并检测其指向的目标文件
  -h, --help      显示此帮助信息并退出

说明:
  命令通过读取文件头部字节(magic bytes)识别图片、压缩包、文档、
  音视频、可执行文件等常见格式, 并对纯文本文件做编码探测。
  未匹配到具体类型时, 文本文件会尽量给出编码, 否则回退为 data。
"""
import argparse
import os
import sys
from typing import Callable, List, Optional, Tuple

CHUNK_SIZE = 8192

# (偏移量, magic 字节, 文字描述, MIME 类型)
MAGIC_RULES: List[Tuple[int, bytes, str, Optional[str]]] = [
    (0, b"\x7fELF", "ELF executable", "application/x-executable"),
    (0, b"\x89PNG\r\n\x1a\n", "PNG image data", "image/png"),
    (0, b"\xff\xd8\xff", "JPEG image data", "image/jpeg"),
    (0, b"GIF87a", "GIF image data", "image/gif"),
    (0, b"GIF89a", "GIF image data", "image/gif"),
    (0, b"BM", "BMP image data", "image/bmp"),
    (0, b"II*\x00", "TIFF image data (little-endian)", "image/tiff"),
    (0, b"MM\x00*", "TIFF image data (big-endian)", "image/tiff"),
    (0, b"8BPS", "Adobe Photoshop image data", "image/vnd.adobe.photoshop"),
    (0, b"%PDF-", "PDF document", "application/pdf"),
    (0, b"%!", "PostScript document", "application/postscript"),
    (0, b"<!DOCTYPE html", "HTML document text", "text/html"),
    (0, b"<?xml", "XML document text", "application/xml"),
    (0, b"PK\x03\x04", "Zip archive", "application/zip"),
    (0, b"PK\x05\x06", "Zip archive (empty)", "application/zip"),
    (0, b"PK\x07\x08", "Zip archive (spanned)", "application/zip"),
    (0, b"\x1f\x8b", "gzip compressed data", "application/gzip"),
    (0, b"BZh", "bzip2 compressed data", "application/x-bzip2"),
    (0, b"\xfd7zXZ\x00", "xz compressed data", "application/x-xz"),
    (0, b"7z\xbc\xaf\x27\x1c", "7-Zip archive", "application/x-7z-compressed"),
    (0, b"Rar!\x1a\x07\x00", "RAR archive (v5)", "application/vnd.rar"),
    (0, b"Rar!\x1a\x07", "RAR archive", "application/vnd.rar"),
    (0, b"\x1f\x9d", "compress'd data (Z)", "application/x-compress"),
    (0, b"\x04\x22\x4d\x18", "LZ4 compressed data", "application/x-lz4"),
    (0, b"\x28\xb5\x2f\xfd", "Zstandard compressed data", "application/zstd"),
    (0, b"\x00\x00\x01\x00", "ICO image data", "image/x-icon"),
    (0, b"\x00\x00\x02\x00", "CUR image data", "image/x-icon"),
    (0, b"OggS", "Ogg data", "application/ogg"),
    (0, b"\x1a\x45\xdf\xa3", "Matroska/WebM data", "video/webm"),
    (0, b"fLaC", "FLAC audio data", "audio/flac"),
    (0, b"ID3", "MP3 audio (with ID3 tag)", "audio/mpeg"),
    (0, b"SQLite format 3\x00", "SQLite 3 database", "application/vnd.sqlite3"),
    (0, b"D0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "Microsoft OLE2 Compound Document", "application/x-ole-storage"),
    (0, b"{\rtf", "Rich Text Format", "application/rtf"),
    (0, b"MThd", "MIDI audio", "audio/midi"),
    (0, b"\xfe\xed\xfa\xce", "Mach-O executable (32-bit, big-endian)", "application/x-mach-binary"),
    (0, b"\xfe\xed\xfa\xcf", "Mach-O executable (64-bit, big-endian)", "application/x-mach-binary"),
    (0, b"\xce\xfa\xed\xfe", "Mach-O executable (32-bit, little-endian)", "application/x-mach-binary"),
    (0, b"\xcf\xfa\xed\xfe", "Mach-O executable (64-bit, little-endian)", "application/x-mach-binary"),
    (0, b"\xca\xfe\xba\xbe", "Java class file", "application/java-vm"),
    (4, b"ftyp", "ISO Media (MP4/M4V/Mov)", "video/mp4"),
    (257, b"ustar", "tar archive", "application/x-tar"),
]

MatchResult = Tuple[str, Optional[str]]
FuncRule = Callable[[bytes], Optional[MatchResult]]


def _check_riff(data: bytes) -> Optional[MatchResult]:
    if data[:4] != b"RIFF":
        return None
    sub = data[8:12]
    if sub == b"WEBP":
        return "WebP image data", "image/webp"
    if sub == b"WAVE":
        return "WAVE audio", "audio/x-wav"
    if sub == b"AVI ":
        return "AVI video", "video/x-msvideo"
    if sub == b"ANI ":
        return "ANI animated cursor", "application/octet-stream"
    return "RIFF data", "application/octet-stream"


def _check_pe(data: bytes) -> Optional[MatchResult]:
    if data[:2] != b"MZ":
        return None
    if len(data) < 0x40:
        return "MS-DOS executable", "application/x-dosexec"
    pe_off = int.from_bytes(data[0x3c:0x40], "little")
    if pe_off + 4 <= len(data) and data[pe_off:pe_off + 4] == b"PE\x00\x00":
        machine = data[pe_off + 4:pe_off + 6]
        if machine == b"\xb4\x64":
            return "PE32+ executable (Windows x86-64)", "application/x-dosexec"
        return "PE32 executable (Windows)", "application/x-dosexec"
    return "MS-DOS executable", "application/x-dosexec"


def _check_mp3_frame(data: bytes) -> Optional[MatchResult]:
    # 排除 UTF-16 BOM(FF FE / FE FF)造成的误判
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return None
    if data and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "MPEG audio (MP3)", "audio/mpeg"
    return None


FUNC_RULES: List[FuncRule] = [
    _check_riff,
    _check_pe,
    _check_mp3_frame,
]


def detect_text(data: bytes) -> Optional[MatchResult]:
    """对疑似文本的内容做编码探测, 非文本返回 None。"""
    if len(data) == 0:
        return "empty", "application/x-empty"
    if data[:3] == b"\xef\xbb\xbf":
        return "UTF-8 Unicode text (with BOM)", "text/plain; charset=utf-8"
    if data[:4] == b"\xff\xfe\x00\x00":
        return "UTF-32 Unicode text (UTF-32LE)", "text/plain; charset=utf-32le"
    if data[:4] == b"\x00\x00\xfe\xff":
        return "UTF-32 Unicode text (UTF-32BE)", "text/plain; charset=utf-32be"
    if data[:2] == b"\xff\xfe":
        return "UTF-16 Unicode text (UTF-16LE)", "text/plain; charset=utf-16le"
    if data[:2] == b"\xfe\xff":
        return "UTF-16 Unicode text (UTF-16BE)", "text/plain; charset=utf-16be"
    # 出现 NUL 字节强烈暗示二进制内容
    if b"\x00" in data[:512]:
        return None
    try:
        data.decode("utf-8")
        return "UTF-8 Unicode text", "text/plain; charset=utf-8"
    except UnicodeDecodeError:
        pass
    try:
        import chardet
        result = chardet.detect(data)
        if result:
            enc = result.get("encoding")
            conf = result.get("confidence") or 0.0
            if enc and conf >= 0.7:
                return "%s text" % enc, "text/plain; charset=%s" % enc.lower()
    except Exception:
        pass
    return None


def detect(real_path: str) -> MatchResult:
    with open(real_path, "rb") as fh:
        data = fh.read(CHUNK_SIZE)
    for offset, magic, desc, mime in MAGIC_RULES:
        end = offset + len(magic)
        if len(data) >= end and data[offset:end] == magic:
            return desc, mime
    for func in FUNC_RULES:
        result = func(data)
        if result is not None:
            return result
    text_result = detect_text(data)
    if text_result is not None:
        return text_result
    return "data", "application/octet-stream"


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(text.encode(enc, "replace").decode(enc))


def main(paths: List[str], brief: bool = False, mime: bool = False,
         follow: bool = False) -> int:
    for path in paths:
        desc: str
        m: Optional[str]
        if os.path.islink(path) and not follow:
            target = os.readlink(path)
            desc, m = "symbolic link to %s" % target, "inode/symlink"
        else:
            real = path
            if follow and os.path.islink(path):
                real = os.path.realpath(path)
            if os.path.isdir(real):
                desc, m = "directory", "inode/directory"
            else:
                try:
                    desc, m = detect(real)
                except OSError as e:
                    sys.stderr.write("%s: cannot open: %s\n" % (path, e))
                    continue
        value = m if (mime and m) else desc
        if brief:
            _safe_print(value)
        else:
            _safe_print("%s: %s" % (path, value))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("paths", nargs="+", help="待检测的文件/目录路径(可多个)")
    parser.add_argument("-b", "--brief", action="store_true",
                        help="不输出文件名, 只输出类型描述")
    parser.add_argument("-i", "--mime", action="store_true",
                        help="输出 MIME 类型而不是文字描述")
    parser.add_argument("-L", "--dereference", action="store_true",
                        help="对符号链接解析并检测其指向的目标文件")
    args = parser.parse_args()
    sys.exit(main(args.paths, args.brief, args.mime, args.dereference))
