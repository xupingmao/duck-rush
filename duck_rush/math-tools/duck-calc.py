'''
Author: xupingmao 578749341@qq.com
Date: 2023-12-17 23:04:16
LastEditors: xupingmao 578749341@qq.com
LastEditTime: 2023-12-17 23:07:32
FilePath: /901_duck_rush/duck_rush/math-tools/duck-calc.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
# encoding=utf-8
import fire


def print_help():
    print("""usage: duck-calc expression

example:
    duck-calc "10*20+5"
    """)

def main(expression=""):
    if expression == "":
        print_help()
        return
    
    result = eval(expression)
    print(result)

if __name__ == "__main__":
    fire.Fire(main)
