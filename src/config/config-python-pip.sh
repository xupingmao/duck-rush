# init python pip source
# @name set-python-pip-source
# 豆瓣：https://pypi.douban.com/simple
# 阿里：https://mirrors.aliyun.com/pypi/simple

pushd .

mkdir -p ~/.pip
cd ~/.pip && touch pip.conf

echo "
[global]
index-url = http://pypi.douban.com/simple
[install]
use-mirrors =true
mirrors =http://pypi.douban.com/simple/
trusted-host =pypi.douban.com
" > pip.conf;

echo configuration done!;

popd

