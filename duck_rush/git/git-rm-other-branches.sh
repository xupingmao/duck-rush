git pull

current=$(git symbolic-ref --short -q HEAD)
echo "当前分支是: $current";

for branch in $(git branch | grep -V master | grep -V $current); do
    echo "删除分支 $branch";
    git branch -D $branch;
done
