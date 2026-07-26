# encoding=utf-8
import os

CODE = """call 你的命令

if %errorlevel% neq 0 (goto failed)

:success
echo execute success!
exit

:failed
echo execute failed!
pause

"""

def main():
    """创建调用命令的包装"""
    call_bat_name = "./call-cmd-example.bat"
    if not os.path.exists(call_bat_name):
        with open(call_bat_name, "w+") as fp:
            fp.write(CODE)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        if __doc__ is not None:
            print(__doc__.strip())
        else:
            print("Usage: " + sys.argv[0] + " [options]")
        sys.exit(0)

    main()
