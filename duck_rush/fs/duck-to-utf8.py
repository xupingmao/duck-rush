import shutil
import os
import chardet
import fire

def convert_file(filename: str, skip_backup = False):
    if not skip_backup:
        shutil.copyfile(filename, filename + ".bak")

    encoding = "utf-8"
    target_encoding = "utf-8"

    with open(filename, "rb+") as fp:
        buf = fp.read(1024*10)
        result = chardet.detect(buf)
        encoding = result["encoding"]

    if encoding == target_encoding:
        return

    new_filename = filename + ".new"
    with open(filename, "r+", encoding=encoding) as fp:
        with open(new_filename, "w+", encoding=target_encoding) as new_fp:
            bufsize = 1024 * 10
            while True:
                buf = fp.read(bufsize)
                new_fp.write(buf)
                if not buf:
                    break
    
    os.remove(filename)
    os.rename(new_filename, filename)

def convert(filename:str, skip_backup = False):
    if os.path.isdir(filename):
        dirname = filename
        for child in os.listdir(filename):
            # todo check text file
            childpath = os.path.join(dirname, child)
            convert_file(childpath, skip_backup=skip_backup)
    else:
        convert_file(filename, skip_backup=skip_backup)

if __name__ == "__main__":
    fire.Fire(convert)


