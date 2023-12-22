# encoding=utf-8

import os
import subprocess
import fire

def my_popen(cmd, debug=False):
    if debug:
        print(f"DEBUG: cmd: {cmd}")
    proc = subprocess.Popen(cmd,
                            shell=True,
                            stdout=subprocess.PIPE)
    return proc.stdout
    

def main(encoding="utf-8", debug=False):
    fp = my_popen("git log --format=%aN", debug=debug)
    user_set = set()
    for line in fp.readlines():
        user_name = line.decode(encoding)
        user_set.add(user_name.strip())
    
    users = sorted(user_set)
    for user_name in users:
        stats_fp = my_popen(f"git log --author=\"{user_name}\" --pretty=tformat: --numstat", debug=debug)
        add = 0
        sub = 0
        loc = 0
        for num_line in stats_fp.readlines():
            num_line = num_line.decode(encoding)
            parts = num_line.split()
            if len(parts) < 3:
                continue
            if parts[0] == "-" or parts[1] == "-":
                continue
            a = int(parts[0])
            b = int(parts[1])
            fname = parts[2]
            if fname == "go.sum":
                continue
            add += a
            sub += b
            loc += a - b
        print(f"{user_name}: added lines: {add}, removed lines: {sub}, total lines: {loc}")


if __name__ == "__main__":
    fire.Fire(main)
    
