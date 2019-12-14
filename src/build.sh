mkdir -p bin;

for fpath in $(find . -name "*.c") ; do
    gcc $fpath;
    fname=$(basename $fpath);
    mv a.out ./bin/$fname.out;
done

