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
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        if __doc__ is not None:
            print(__doc__.strip())
        else:
            print("Usage: " + sys.argv[0] + " [options]")
        sys.exit(0)
