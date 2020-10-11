
if [[ $# -ne 1 ]]; then
    fname=$(basename $0)
    echo "usage: $fname branchName"
    exit 0
fi

git pull;
git checkout -b $1 origin/$1;

