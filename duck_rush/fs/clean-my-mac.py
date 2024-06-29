
import fire
import os

def get_dir_size(dirname=""):
    return os.popen(f"du -sh {dirname}").read()

def print_dir_size(dirname="", message=""):
    print(f"\n{message}")
    print(f"文件夹: {dirname}")
    dirsize = get_dir_size(dirname)
    print(f"文件夹大小: {dirsize}\n")

def clean_my_mac():
    watchOS_runtime="/Applications/Xcode.app/Contents/Developer/Platforms/WatchOS.platform/Library/Developer/CoreSimulator/Profiles/Runtimes/watchOS.simruntime"
    tvOS_runtime="/Applications/Xcode.app/Contents/Developer/Platforms/AppleTVOS.platform/Library/Developer/CoreSimulator/Profiles/Runtimes/tvOS.simruntime"

    if os.path.exists(watchOS_runtime):
        print_dir_size(watchOS_runtime, "watchOS运行时")
    
    if os.path.exists(tvOS_runtime):
        print_dir_size(tvOS_runtime, "tvOS运行时")

if __name__ == "__main__":
    fire.Fire(clean_my_mac)