# init python pip source
# @name set-python-pip-source
# 清华大学的源: https://pypi.tuna.tsinghua.edu.cn/simple/
# 豆瓣：https://pypi.douban.com/simple
# 阿里：https://mirrors.aliyun.com/pypi/simple

python3 -m pip config set global.index-url  https://pypi.tuna.tsinghua.edu.cn/simple/


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

