case "$1" in
  -h|--help)
    echo "Usage: $(basename "$0") [options]"
    exit 0
    ;;
esac

# Normal
echo "Hello"

# No NewLine
echo -n "No NewLine"
