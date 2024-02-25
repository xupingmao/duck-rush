# encoding=utf-8
import os
from duck_rush.utils import fs_util

class XnotePack:
    def __init__(self, root_dir=""):
        self.encoding="utf-8"
        self.import_dict = {}
        self.entry_file = ""
        self.packed_files = set()
        self.root_dir = root_dir
        self.skip_blank_line = True

    def _get_abs_path(self, fpath):
        if fpath.startswith("."):
            fpath = os.path.join(self.root_dir, fpath)
        return os.path.abspath(fpath)

    def set_entry_file(self, entry_file=""):
        self.entry_file = self._get_abs_path(entry_file)
        
    def build(self, target_file=""):
        lines = self.do_build([], self.entry_file)
        with open(target_file, "w+", encoding=self.encoding) as fp:
            fp.writelines(lines)
    
    def do_build(self, lines=[], entry_file=""):
        tokenizer = CodeTokenizer()
        
        with open(entry_file, "r+", encoding=self.encoding) as fp:
            for line in fp.readlines():
                replace_file = ""
                
                line_strip = line.strip()
                if line_strip.startswith("import"):
                    parse_result = tokenizer.parse(line_strip)
                    t1, t2, t3, t4, t5 = parse_result.get_list(5)
                    # from .xxx import *
                    if t1.value == "from" and t2.value == "." and t3.type == "name" and t4.value == "import" and t5.value == "*":
                        replace_file = t3.value
                        # TODO 转换成本地文件
                        if replace_file in self.packed_files:
                            print(f"file already packed: {replace_file}")
                            continue
                if line_strip == "" and self.skip_blank_line:
                    continue
                if replace_file != "":
                    self.packed_files.add(replace_file)
                    replace_file_relative = fs_util.get_relative_path(replace_file, self.root_dir)
                    lines.append(f"# include start {replace_file_relative}\n")
                    self.do_build(lines, replace_file)
                    lines.append(f"# include end {replace_file_relative}\n")
                else:
                    lines.append(line)
        return lines
