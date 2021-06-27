
if [[ $# -ne 1 ]]; then
    fname=$(basename $0)
    echo "usage: $fname branchName"
    exit 0
fi

git pull;
git checkout -b $1 origin/$1;

if [[ $? -eq 128 ]]; then
    echo "checkout远程分支失败，尝试checkout本地分支: $1"
    git checkout $1;
fi

git pull;
