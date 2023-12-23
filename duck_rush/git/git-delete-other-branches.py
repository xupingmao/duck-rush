# encoding=utf-8
import os
import fire
import sys

duck_rush_dir = os.environ.get("DUCK_RUSH_DIR", "")
if duck_rush_dir not in sys.path:
    sys.path.append(duck_rush_dir)

from duck_rush.utils import os_util

def get_current_branch():
    return os.popen("git symbolic-ref --short -q HEAD").read()

def delete_other_branches():
    current_branch = get_current_branch()
    for line in os.popen("git branch").readlines():
        line = line.strip()
        if line.startswith("* "):
            # 当前分支
            continue

        if line == "master":
            continue

        if line == current_branch:
            continue

        os_util.exec_cmd(f"git branch -D {line}")

if __name__ == "__main__":
    fire.Fire(delete_other_branches)