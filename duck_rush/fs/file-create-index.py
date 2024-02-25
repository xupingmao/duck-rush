# -*- coding:utf-8 -*-
"""
@Author: xupingmao
@email: 578749341@qq.com
@Date: 2024-02-25 16:40:47
@LastEditors: xupingmao
@LastEditTime: 2024-02-25 17:41:14
@FilePath: \duck-rush\duck_rush\fs\file-create-index.py
@Description: Description
"""
# encoding=utf-8
import os
import html
import fire
from urllib.parse import quote

DEFAULT_OUTPUT = "file-index.html"

class IndexItem:
    
    def __init__(self):
        self.name = ""
        self.path = ""
        self.dirs = []
        self.files = []

class IndexBuilder:
    
    index_list = []
    empty_item = IndexItem()
    
    def build(self, dirname="", output=""):
        assert output != ""
        assert dirname != ""
        
        root = IndexItem()
        root.name = dirname
        root.path = dirname
        self.iter_dir(root)
        
        with open(output, "w+") as fp:
            self.index_fp = fp
            fp.write("""<html><head>
                     <style>
                        .dir {
                            background-color: #eee;
                            color: blue;
                        }
                        .file {
                            padding-left: 40px;
                        }
                     </style>
                     </head>
                     <body>""")
            self.build_search()
            self.save_index(root)
            fp.write("</body></html>")
        
    def iter_dir(self, item=empty_item):
        assert item.path != ""
        assert item.name != ""
        
        dirname = item.path
        files = os.listdir(dirname)
        for fname in sorted(files):
            fpath = os.path.join(dirname, fname)
            if os.path.isdir(fpath):
                sub_item = IndexItem()
                sub_item.name = fname
                sub_item.path = fpath
                self.iter_dir(sub_item)
                item.dirs.append(sub_item)
            else:
                item.files.append(fname)
    
    def build_search(self):
        # TODO
        return
        self.index_fp.write("""
        <div class="search-box">
            <input placeholder="搜索" onchange="searchIndexFile(this)"><input type="button" value="搜索">
        </div>
        
        <script>
            function searchIndexFile(ele) {
                var value = ele.value;
            }
        </script>
                            """)
    
    def save_index(self, index=empty_item, indent=0):
        child_indent = indent + 1
        
        if len(index.files) > 0:
            # 有子文件的才输出目录名称
            path = index.path.replace("\\", "/")
            self.index_fp.write(f"<div class=\"indent-{indent} dir\"><a href=\"{quote(path)}\">{html.escape(path)}</a></div>")
            
            for fname in index.files:
                self.index_fp.write(f"<div class=\"indent-{child_indent} file\">{html.escape(fname)}</div>")
        
        for sub_item in index.dirs:
            self.save_index(sub_item, indent=child_indent)
    
def main(dirname=".", output=DEFAULT_OUTPUT):
    builder = IndexBuilder()
    builder.build(dirname=dirname, output=output)

if __name__ == "__main__":
    fire.Fire(main)