# -*- coding: utf-8 -*-
# @since 2018/02/10
# @modified 2020/10/11 13:25:42
# @author xupingmao <578749341@qq.com>
import sublime, sublime_plugin
import time
import os


# Sublime Text 2 的插件路径
# ~/Library/Application Support/Sublime Text 2/Packages/User

PYTHON_DOC_TEMPLATE = """# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since %s
# @modified %s
"""

C_DOC_TEMPLATE = """/**
 * description here
 * @author xupingmao <578749341@qq.com>
 * @since %s
 * @modified %s
 */"""

def say(msg):
    os.system("say %r" % msg)

class MyEventListenerCommand(sublime_plugin.EventListener):
    """
    http://www.sublimetext.com/docs/2/api_reference.html#sublime_plugin.EventListener
    """

    def do_nothing(self):
        pass

    # def on_new(self, view):
    #   pass

    # def on_clone(self, view):
    #   pass

    # def on_load(self, view):
    #   pass

    # def on_close(self, view):
    #   pass
    
    def on_pre_save(self, view):
        datetime_fmt = "%Y/%m/%d %H:%M:%S"
        file_name = view.file_name()
        datetime_str = time.strftime(datetime_fmt)

        if view.size() == 0 and file_name is not None and file_name.endswith(".py"):
            python_doc = PYTHON_DOC_TEMPLATE % (datetime_str, datetime_str)
            edit = view.begin_edit()
            view.insert(edit, 0, python_doc)
            view.end_edit(edit)

        region = view.find("@modified.*", 0)
        if region is not None:
            edit = view.begin_edit()
            new_text = "@modified %s" % time.strftime(datetime_fmt)
            view.replace(edit, region, new_text)
            view.end_edit(edit)

        region = view.find("@" + "pydoc.*", 0)
        if region is not None:
            edit = view.begin_edit()
            python_doc = PYTHON_DOC_TEMPLATE % (datetime_str, datetime_str)
            view.replace(edit, region, python_doc)
            view.end_edit(edit)

        region = view.find("@" + "cdoc.*", 0)
        if region is not None:
            edit = view.begin_edit()
            c_doc = C_DOC_TEMPLATE % (datetime_str, datetime_str)
            view.replace(edit, region, c_doc)
            view.end_edit(edit)


    # def on_post_save(self, view):
    #   pass

    # def on_modified(self, view):
    #   pass

    # def on_selection_modified(self, view):
    #   pass

    # def on_activated(self, view):
    #   pass

    # def on_query_context(self, view, key, operator, operand, match_all):
    #   pass

