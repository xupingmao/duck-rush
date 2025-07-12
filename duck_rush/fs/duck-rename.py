
import xutils
import os
import fire


class DuckRename:
    def encode(self, dirname="./"):
        """对文件名进行base64编码"""
        for fname in os.listdir(dirname):
            new_name = xutils.encode_name(fname)
            old_path = os.path.join(dirname, fname)
            new_path = os.path.join(dirname, new_name)
            os.rename(old_path, new_path)

    def decode(self, dirname="./"):
        """对文件名进行base64解码"""
        for fname in os.listdir(dirname):
            new_name = xutils.decode_name(fname)
            old_path = os.path.join(dirname, fname)
            new_path = os.path.join(dirname, new_name)
            os.rename(old_path, new_path)


if __name__ == "__main__":
    fire.Fire(DuckRename)