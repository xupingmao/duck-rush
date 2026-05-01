import argparse
import os
import re
from typing import List

import pycdlib


def sanitize_iso9660_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    name = re.sub(r"[^A-Z0-9]", "_", name.upper())[:8]
    ext = re.sub(r"[^A-Z0-9]", "_", ext.upper().lstrip("."))[:3]
    result = (name + "." + ext).rstrip(".") or "FILE"
    return result


def create_iso(source_path: str, output_iso: str = "share.iso", volume_label: str = "SHARE") -> None:
    iso = pycdlib.PyCdlib()
    vol_ident_bytes: bytes = volume_label.encode("utf-16-be")[:32]
    vol_ident: str = vol_ident_bytes.decode("utf-16-be").ljust(16)
    iso.new(
        interchange_level=3,
        vol_ident=vol_ident,
        rock_ridge="1.09",
        joliet=True
    )

    if os.path.isfile(source_path):
        files: List[str] = [source_path]
        root_path: str = os.path.dirname(source_path)
    else:
        files = []
        for r, _, f in os.walk(source_path):
            for file in f:
                files.append(os.path.join(r, file))
        root_path = source_path

    for file_path in files:
        rel_path = os.path.relpath(file_path, root_path)
        rr_name: str = rel_path.replace(os.path.sep, "/")
        iso_name: str = sanitize_iso9660_filename(os.path.basename(file_path))
        iso_path = "/" + iso_name
        joliet_path = "/" + rel_path.replace(os.path.sep, "/")
        try:
            iso.add_file(file_path, iso_path=iso_path, joliet_path=joliet_path, rr_name=rr_name)
        except Exception as e:
            print(f"跳过：{file_path} -> {e}")

    iso.write(output_iso)
    iso.close()
    print(f"\n✅ ISO 生成完成：{output_iso}")


def main() -> None:
    parser = argparse.ArgumentParser(description="创建 ISO 镜像工具")
    parser.add_argument("source", help="源文件或文件夹路径")
    parser.add_argument("-o", "--output", default="share.iso", help="输出 ISO 文件名 (默认: share.iso)")
    parser.add_argument("-v", "--volume", default="SHARE", help="卷标名称 (默认: SHARE)")
    args = parser.parse_args()

    create_iso(args.source, args.output, args.volume)


if __name__ == "__main__":
    main()
