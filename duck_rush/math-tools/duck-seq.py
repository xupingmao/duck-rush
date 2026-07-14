# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2024-09-02 00:06:21
LastEditors: xupingmao
LastEditTime: 2024-09-02 00:16:04
FilePath: /duck_rush/duck_rush/math-tools/duck-seq.py
Description: 复刻 GNU seq 命令, 打印数字/字符序列
    用法:
        duck-seq LAST
        duck-seq FIRST LAST
        duck-seq FIRST INCREMENT LAST
        duck-seq 字符首 字符尾            # 字符序列, 如 a z
        duck-seq 字符首 步长 字符尾        # 步长可为整数(a 2 z)或字符(a c z)
    选项:
        -f, --format FORMAT     printf 风格格式, 如 %03g / item-%g / %s
        -s, --separator SEP     元素间分隔符(默认换行)
        -w, --equal-width       等宽输出, 前导零补齐
        --version               显示版本
    注: 以 '-' 开头的数字(如负数)需放在 -- 之后, 例如: duck-seq -- -5 -1
'''

import sys
import argparse


def count_decimals(s: str) -> int:
    '''统计字符串中小数点后的位数, 用于决定默认显示精度'''
    s = s.strip()
    if '.' in s:
        return len(s.split('.')[1])
    return 0


def build_sequence(first: float, increment: float, last: float):
    '''按步长累加生成序列(浮点容差避免边界值因精度误差丢失)'''
    if increment == 0:
        raise ValueError("步长(increment)不能为 0")
    result = []
    eps = 1e-10 * max(1.0, abs(first), abs(increment), abs(last))
    cur = first
    if increment > 0:
        while cur <= last + eps:
            result.append(cur)
            cur += increment
    else:
        while cur >= last - eps:
            result.append(cur)
            cur += increment
    return result


def pad_equal_width(s: str, width: int) -> str:
    '''等宽补齐: 非负数字整体前导零补齐, 负数补齐绝对值部分'''
    if len(s) >= width:
        return s
    if s.startswith('-'):
        return '-' + s[1:].zfill(width - 1)
    return s.zfill(width)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="duck-seq",
        description="打印数字序列, 复刻 GNU seq")
    parser.add_argument("numbers", nargs="+",
                        help="数字参数: LAST | FIRST LAST | FIRST INCREMENT LAST")
    parser.add_argument("-f", "--format", default=None,
                        help="printf 风格格式, 如 %%03g / item-%%g")
    parser.add_argument("-s", "--separator", default="\n",
                        help="数字之间的分隔符(默认换行)")
    parser.add_argument("-w", "--equal-width", action="store_true",
                        help="等宽输出, 用前导零补齐")
    parser.add_argument("--version", action="store_true",
                        help="显示版本信息")
    # --version 允许单独使用(不依赖必填的数字参数)
    if "--version" in sys.argv:
        print("duck-seq 1.0")
        return

    args = parser.parse_args()

    if args.version:
        print("duck-seq 1.0")
        return

    nums = args.numbers
    if len(nums) > 3:
        sys.stderr.write("duck-seq: 参数过多, 最多支持 3 个参数\n")
        sys.exit(1)

    if args.format is not None and args.equal_width:
        sys.stderr.write("duck-seq: 等宽输出时不能指定格式字符串\n")
        sys.exit(1)

    if args.format is not None and '%' not in args.format:
        sys.stderr.write("duck-seq: 格式 ‘%s’ 中没有 %%%% 指令\n" % args.format)
        sys.exit(1)

    def is_single_alpha(s: str) -> bool:
        return len(s) == 1 and s.isalpha()

    # 首尾都是单个字母 -> 字符序列模式
    char_mode = is_single_alpha(nums[0]) and is_single_alpha(nums[-1])

    if char_mode:
        start = ord(nums[0])
        end = ord(nums[-1])
        if len(nums) <= 2:
            step = 1
        else:
            mid = nums[1]
            if is_single_alpha(mid):
                step = ord(mid) - start          # 如 a c z -> 步长=2
            else:
                try:
                    step = int(mid)               # 如 a 2 z -> 步长=2
                except ValueError:
                    sys.stderr.write(
                        "duck-seq: 字符模式的步长必须是整数或单个字符: %s\n" % mid)
                    sys.exit(1)

        try:
            seq = build_sequence(float(start), float(step), float(end))
        except ValueError as e:
            sys.stderr.write("duck-seq: %s\n" % e)
            sys.exit(1)

        parts = [chr(int(round(v))) for v in seq]

        if args.format is not None:
            try:
                parts = [args.format % c for c in parts]
            except (TypeError, ValueError) as e:
                sys.stderr.write("duck-seq: 格式错误: %s\n" % e)
                sys.exit(1)
        elif args.equal_width:
            width = max(len(p) for p in parts)
            parts = [pad_equal_width(p, width) for p in parts]
    else:
        try:
            values = [float(x) for x in nums]
        except ValueError:
            sys.stderr.write("duck-seq: 无效的数字参数: %s\n" % " ".join(nums))
            sys.exit(1)

        if len(values) == 1:
            first, increment, last = 1.0, 1.0, values[0]
        elif len(values) == 2:
            first, increment, last = values[0], 1.0, values[1]
        else:
            first, increment, last = values[0], values[1], values[2]

        # 默认显示精度: 取所有操作数的最大小数位数
        decimals = 0
        for s in nums:
            decimals = max(decimals, count_decimals(s))
        default_fmt = "%%.%df" % decimals

        try:
            seq = build_sequence(first, increment, last)
        except ValueError as e:
            sys.stderr.write("duck-seq: %s\n" % e)
            sys.exit(1)

        if args.equal_width:
            parts = [default_fmt % v for v in seq]
            width = max(len(p) for p in parts)
            parts = [pad_equal_width(p, width) for p in parts]
        elif args.format is not None:
            parts = [args.format % v for v in seq]
        else:
            parts = [default_fmt % v for v in seq]

    if parts:
        out = args.separator.join(parts) + "\n"
        # 直接写字节, 避免 Windows 下文本模式把 \n 转成 \r\n
        sys.stdout.buffer.write(out.encode("utf-8"))
    else:
        sys.stdout.buffer.write(b"")


if __name__ == "__main__":
    main()
