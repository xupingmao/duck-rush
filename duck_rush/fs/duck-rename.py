
import xutils
import os
import fire

def encode_dirname(dirname: str):
    for fname in os.listdir(dirname):
        new_name = xutils.encode_name(fname)
        old_path = os.path.join(dirname, fname)
        new_path = os.path.join(dirname, new_name)
        os.rename(old_path, new_path)

def decode_dirname(dirname: str):
    for fname in os.listdir(dirname):
        new_name = xutils.decode_name(fname)
        old_path = os.path.join(dirname, fname)
        new_path = os.path.join(dirname, new_name)
        os.rename(old_path, new_path)


def main(dirname="./", action="encode"):
    if action == "encode":
        return encode_dirname(dirname)
    if action == "decode":
        return decode_dirname(dirname)
    print(f"未知操作: {action}")


if __name__ == "__main__":
    fire.Fire(main)