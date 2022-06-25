
current=$(git symbolic-ref --short -q HEAD)
git pull origin $current
