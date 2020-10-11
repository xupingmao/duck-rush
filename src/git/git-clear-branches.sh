git pull
git checkout master
git pull

current=$(git symblic-ref --short -q HEAD)
echo "current branch is $current";

for branch in $(git branch | grep -V master); do
    echo rm branch $branch;
    git branch -D $branch;
done
