

# 这个小工具可以自动配置maven的shell路径
# 使用方式

print_usage() {
    cmd_name=$(basename $0)
    echo "工具名: maven路径自动配置"
    echo ""
    echo "使用帮助:"
    echo "  1. cd到maven的解压目录"
    echo "  2. 执行[$cmd_name]命令"
}

if [ "$1" = '-h' ]; then
    print_usage;
elif [ -f ./bin/mvn ]; then
    config-shell-path.py ./bin;
    reload-bash-profile;
    echo "成功添加maven路径!";
elif [ -f ./mvn ]; then
    config-shell-path.py ./;
    reload-bash-profile;
    echo "成功添加maven路径!";
else
    path=$(pwd)
    echo "未能识别maven路径: [$path] 请检查是否在maven目录中";
fi
