# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/04/18 17:26:07
# @modified 2021/04/18 17:26:11
# @filename file_header_listener.py

import sublime
import sublime_plugin

class FileHeaderListener(sublime_plugin.EventListener):

    def on_pre_save(self, view):
        # sublime.message_dialog("on_pre_save start")
        try:
            view.run_command("file_header")
            # sublime.message_dialog("on_pre_save success")
        except Exception as e:
            sublime.error_message("on_pre_save end: %s" % str(e))

