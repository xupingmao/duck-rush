

echo_line() {
    if [[ $2 -ne 0 ]]
    then
        printf "%-15s%s\n" $1 $2
    fi
}

count_line_and_echo() {
    echo_line $1 $(find . -name "$2" -type f | xargs -I{} cat "{}" 2>/dev/null \ | wc -l)
}


printf "%-15s%s\n" "Code Type" "Lines"
count_line_and_echo Java "*.java"
count_line_and_echo Python "*.py"
count_line_and_echo Php "*.php"
count_line_and_echo Shell "*.sh"
count_line_and_echo C-Header "*.h"
count_line_and_echo C   "*.c"
count_line_and_echo C++ Header "*.hpp"
count_line_and_echo C++ "*.cpp"
count_line_and_echo Xml "*.xml"
count_line_and_echo Html "*.html"
count_line_and_echo CSS "*.css"
count_line_and_echo JavaScript "*.js"

