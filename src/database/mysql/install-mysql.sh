###
 # @Author       : xupingmao
 # @email        : 578749341@qq.com
 # @Date         : 2022-09-03 22:55:06
 # @LastEditors  : xupingmao
 # @LastEditTime : 2022-09-04 09:48:36
 # @FilePath     : /xnoted:/projects/duck_rush/src/database/mysql/install-mysql.sh
 # @Description  : 描述
### 

type docker
if [[ $? -ne 0 ]]; then
    echo "请先安装docker"
    exit 1
fi

sudo docker pull mysql:5.7

