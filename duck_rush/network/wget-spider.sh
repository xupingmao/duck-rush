case "$1" in
  -h|--help)
    echo "Usage: $(basename "$0") [options]"
    exit 0
    ;;
esac

wget -c -r -npH -k -e robots=off -Q10m $1
