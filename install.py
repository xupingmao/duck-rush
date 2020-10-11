import os

FILE_PATH  = os.path.abspath(__file__)
HOME_PATH  = os.environ["HOME"]

def find_bash_profile_path():
    bash_profile = os.path.join(HOME_PATH, ".bash_profile")
    if os.path.exists(bash_profile):
        return bash_profile

    bash_rc = os.path.join(HOME_PATH, ".bashrc")
    if os.path.exists(bash_rc):
        return bash_rc
    raise Exception("bash profile not found!")

def load_bash_profile():
    fpath = find_bash_profile_path()
    with open(fpath) as fp:
        return fp.read()

def append_to_bash_profile(cmd):
    fpath = find_bash_profile_path()
    with open(fpath, "a+") as fp:
        fp.write("\n")
        fp.write(cmd)

def add_shell_path(fpath):
    fpath = os.path.abspath(fpath)
    cmd = "PATH=$PATH:%s" % fpath
    bash_profile_text = load_bash_profile()

    os.system("chmod +x %s/*" % fpath)
    
    if cmd not in bash_profile_text:
        append_to_bash_profile(cmd)

add_shell_path("./src/fs")
add_shell_path("./src/text")
add_shell_path("./src/network")



