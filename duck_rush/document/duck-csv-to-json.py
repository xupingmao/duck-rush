
__doc__ = """
Convert a CSV stream/file to a JSONL stream/file.

默认从标准输入读取 CSV，向标准输出写入 JSONL，便于管道使用：
    cat data.csv | duck-csv-to-json > data.jsonl

也可通过 -i/-o 指定文件：
    duck-csv-to-json -i data.csv -o data.jsonl
"""

import csv
import json
import sys
import argparse
import typing


def csv_to_jsonl(in_stream, out_stream) -> int:
    """
    将CSV转换为JSONL并写入输出流

    :param in_stream: 输入流（如 sys.stdin 或打开的文件）
    :param out_stream: 输出流（如 sys.stdout 或打开的文件）
    :return: 转换的行数
    """
    reader = csv.DictReader(in_stream)
    count = 0
    for row in reader:
        json.dump(row, out_stream, ensure_ascii=False)
        out_stream.write('\n')
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description = "将 CSV 转换为 JSONL（默认 stdin -> stdout，支持管道）")
    parser.add_argument("-i", "--input", default = None,
                        help = "输入 CSV 文件，省略时从标准输入读取")
    parser.add_argument("-o", "--output", default = None,
                        help = "输出 JSONL 文件，省略时写入标准输出")
    args = parser.parse_args()

    in_stream = open(args.input, 'r', encoding = 'utf-8') if args.input else sys.stdin
    out_stream = open(args.output, 'w', encoding = 'utf-8') if args.output else sys.stdout
    try:
        count = csv_to_jsonl(in_stream, out_stream)
    finally:
        # 只关闭我们自行打开的流，避免关闭 sys.stdin/sys.stdout
        if args.input:
            in_stream.close()
        if args.output:
            out_stream.close()

    if args.output:
        print(f"成功转换 {count} 行 -> {args.output}", file = sys.stderr)


if __name__ == "__main__":
    main()
