# init python pip source
# @name set-python-pip-source
# 清华大学的源: https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
# 豆瓣：https://pypi.douban.com/simple
# 阿里：https://mirrors.aliyun.com/pypi/simple

import os
import sys
import fire


mirror_mapping = {
    "aliyun": "https://mirrors.aliyun.com/pypi/simple/",
    "tsinghua": "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple",
    "douban": "https://pypi.douban.com/simple",
}

def setup_pip_config(mirror="aliyun"):
    mirror_url = mirror_mapping[mirror]
    os.system(f"{sys.executable} -m pip config set global.index-url {mirror_url} --user")


# pushd .

# mkdir -p ~/.pip
# cd ~/.pip && touch pip.conf

# echo "
# [global]
# index-url = http://pypi.douban.com/simple
# [install]
# use-mirrors =true
# mirrors =http://pypi.douban.com/simple/
# trusted-host =pypi.douban.com
# " > pip.conf;

# echo configuration done!;

# popd



if __name__ == "__main__":
    fire.Fire(setup_pip_config)
