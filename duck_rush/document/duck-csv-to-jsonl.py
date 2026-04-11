
__doc__ = """
Convert a CSV file to a JSONL file.
"""

import csv
import json
import sys
import os


def csv_to_jsonl(csv_file: str, jsonl_file: str) -> bool:
    """
    将CSV文件转换为JSONL文件
    :param csv_file: CSV文件路径
    :param jsonl_file: JSONL文件路径
    :return: 转换是否成功
    """
    try:
        # 打开CSV文件进行读取
        with open(csv_file, 'r', encoding='utf-8') as f:
            # 创建CSV读取器
            reader = csv.DictReader(f)
            
            # 打开JSONL文件进行写入
            with open(jsonl_file, 'w', encoding='utf-8') as out_f:
                # 逐行读取CSV并转换为JSONL
                for row in reader:
                    # 将字典转换为JSON字符串并写入文件
                    json.dump(row, out_f, ensure_ascii=False)
                    out_f.write('\n')
        
        print(f"成功将 {csv_file} 转换为 {jsonl_file}")
        return True
        
    except Exception as e:
        print(f"转换过程中出错: {e}", file=sys.stderr)
        return False


def main() -> None:
    """
    主函数
    """
    # 检查命令行参数
    if len(sys.argv) != 3:
        print("使用方法:")
        print(f"  python {os.path.basename(__file__)} <input_csv_file> <output_jsonl_file>")
        print("\n示例:")
        print(f"  python {os.path.basename(__file__)} data.csv data.jsonl")
        return
    
    # 获取输入和输出文件路径
    csv_file: str = sys.argv[1]
    jsonl_file: str = sys.argv[2]
    
    # 检查输入文件是否存在
    if not os.path.exists(csv_file):
        print(f"错误: 输入文件 {csv_file} 不存在", file=sys.stderr)
        return
    
    print("=== Duck CSV to JSONL 工具 ===")
    print("用于将CSV文件转换为JSONL文件")
    print("\n")
    
    # 执行转换
    csv_to_jsonl(csv_file, jsonl_file)


if __name__ == "__main__":
    main()