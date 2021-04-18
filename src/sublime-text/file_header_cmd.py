# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/04/18 17:26:24
# @modified 2021/04/18 17:26:31
# @filename file_header_cmd.py

import sublime
import sublime_plugin
import time
import os

PYTHON_DOC_TEMPLATE = """# -*- coding:utf-8 -*-
# @author xupingmao
# @since %s
# @modified %s
# @filename %s
"""

DATETIME_FMT = "%Y/%m/%d %H:%M:%S"

class FileHeaderCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        view = self.view
        # sublime.message_dialog("MySaveCommand start")

        file_name = view.file_name()

        # sublime.message_dialog("size=%s, filename=%s" % (view.size(), file_name))

        if view.size() == 0 and file_name is not None and file_name.endswith(".py"):
            datetime_str = time.strftime(DATETIME_FMT)
            python_doc = PYTHON_DOC_TEMPLATE % (datetime_str, datetime_str, file_name)
            view.insert(edit, 0, python_doc)

        # 修改时间
        self.do_update_mtime(view, edit)

        # 文件名
        self.do_update_fname(view, edit)


    def do_update_mtime(self, view, edit):
        region = view.find("@modified.*", 0)
        if region is not None:
            text = view.substr(region)
            if text == "@modified %s":
                return
            # edit = view.begin_edit()
            new_text = "@modified %s" % time.strftime(DATETIME_FMT)
            view.replace(edit, region, new_text)


    def do_update_fname(self, view, edit):
        file_name = view.file_name()
        region = view.find("@filename.*", 0)
        if region is not None:
            text = view.substr(region)
            if text == "@filename %s":
                return
            basename = os.path.basename(file_name)
            new_text = "@filename %s" % basename
            if text != new_text:
                view.replace(edit, region, new_text)


