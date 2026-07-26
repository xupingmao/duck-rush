case "$1" in
  -h|--help)
    echo "Usage: $(basename "$0") [options]"
    exit 0
    ;;
esac
mvn -Dmaven.test.skip=false -e test verify
