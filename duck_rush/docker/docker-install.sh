

# Mac OS

a=`uname  -a`

b="Darwin"
c="centos"
d="ubuntu"

if [[ $a =~ $b ]];then
    echo "检测到mac系统"
    wget -c https://download.docker.com/mac/stable/Docker.dmg
elif [[ $a =~ $c ]];then
    echo "centos"
elif [[ $a =~ $d ]];then
    echo "ubuntu"
else
    echo $a
fi

