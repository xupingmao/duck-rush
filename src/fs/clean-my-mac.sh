
echo "清理xcode文件..."

watchOS_runtime=/Applications/Xcode.app/Contents/Developer/Platforms/WatchOS.platform/Library/Developer/CoreSimulator/Profiles/Runtimes/watchOS.simruntime
tvOS_runtime=/Applications/Xcode.app/Contents/Developer/Platforms/AppleTVOS.platform/Library/Developer/CoreSimulator/Profiles/Runtimes/tvOS.simruntime

function get_dir_size() {
    size=$(du -sh "$1");
    for t in $size; do
        echo $t;
        break;
    done
}

if [ -d $watchOS_runtime ]; then
    echo "watchOS运行时"
    echo $watchOS_runtime
    echo "文件夹大小:$(du -sh $watchOS_runtime)"
fi

if [ -d $tvOS_runtime ]; then
    echo "tvOS运行时"
    echo "文件夹: $tvOS_runtime"
    echo "文件夹大小:$(get_dir_size $tvOS_runtime)"
fi
