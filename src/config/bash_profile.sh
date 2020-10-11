
# 终端配置
# 位于~/.bash_profile

# Get the aliases and functions
if [ -f ~/.bashrc ]; then
        . ~/.bashrc
fi

if [ -z "$PS1" ]; then
   return
fi

# User specific environment and startup programs
# 用户自定义脚本目录
PATH=$PATH:$HOME/bin

# 路径高亮
PS1="\n\e[1;37m[\e[m\e[1;32m\u\e[m\e[1;33m@\e[m\e[1;35m\H\e[m \e[4m\w\e[m\e[1;37m]\e[m\e[1;36m\e[m\n\$ "

# \w 全路径
# \u 用户名
# \n 换行
# \e[1;37m 颜色, 设置颜色之后会一直保持直到再次被修改
# \e[m 默认配置

# LS的颜色配置
# LS_COLORS="no=00:fi=00:di=00;36:ln=00;36:pi=40;33:so=00;35:bd=40;33;01:cd=40;33;01:or=01;05;37;41:mi=01;05;37;41:ex=00;32:*.cmd=00;32:*.exe=00;32:*.com=00;32:*.btm=00;32:*.bat=00;32:*.sh=00;32:*.csh=00;32:*.tar=00;31:*.tgz=00;31:*.arj=00;31:*.taz=00;31:*.lzh=00;31:*.zip=00;31:*.z=00;31:*.Z=00;31:*.gz=00;31:*.bz2=00;31:*.bz=00;31:*.tz=00;31:*.rpm=00;31:*.cpio=00;31:*.jpg=00;35:*.gif=00;35:*.bmp=00;35:*.xbm=00;35:*.xpm=00;35:*.png=00;35:*.tif=00;35:"

# 设置目录颜色
export CLICOLOR=1
export PATH
export JAVA_HOME=$(/usr/libexec/java_home)

# 别名
alias ll="ls -lh"
alias la="ls -lha"
alias recent="find . -mtime -3"
alias reload-bash-profile="source ~/.bash_profile"


# PS1配置参数详解
# \d ：代表日期，格式为weekday month date，例如："Mon Aug 1"
# \H ：完整的主机名称。例如：我的机器名称为：fc4.linux，则这个名称就是fc4.linux
# \h ：仅取主机的第一个名字，如上例，则为fc4，.linux则被省略
# \t ：显示时间为24小时格式，如：HH：MM：SS
# \T ：显示时间为12小时格式
# \A ：显示时间为24小时格式：HH：MM
# \u ：当前用户的账号名称
# \v ：BASH的版本信息
# \w ：完整的工作目录名称。家目录会以 ~代替
# \W ：利用basename取得工作目录名称，所以只会列出最后一个目录
# \# ：下达的第几个命令
# \$ ：提示字符，如果是root时，提示符为：# ，普通用户则为：$

