__doc__ = """
将 JSONL 文件转换为 CSV 文件
"""

import json
import csv
import sys
import os
from typing import List, Dict, Any


def jsonl_to_csv(jsonl_file: str, csv_file: str) -> bool:
    """
    将JSONL文件转换为CSV文件
    :param jsonl_file: JSONL文件路径
    :param csv_file: CSV文件路径
    :return: 转换是否成功
    """
    try:
        # 读取JSONL文件并收集所有数据
        data: List[Dict[str, Any]] = []
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
        
        if not data:
            print("错误: JSONL文件为空或格式不正确", file=sys.stderr)
            return False
        
        # 提取所有字段名
        fieldnames: set = set()
        for item in data:
            fieldnames.update(item.keys())
        fieldnames: List[str] = list(fieldnames)
        
        # 写入CSV文件
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        print(f"成功将 {jsonl_file} 转换为 {csv_file}")
        print(f"转换了 {len(data)} 条记录")
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
        print(f"  python {os.path.basename(__file__)} <input_jsonl_file> <output_csv_file>")
        print("\n示例:")
        print(f"  python {os.path.basename(__file__)} data.jsonl data.csv")
        return
    
    # 获取输入和输出文件路径
    jsonl_file: str = sys.argv[1]
    csv_file: str = sys.argv[2]
    
    # 检查输入文件是否存在
    if not os.path.exists(jsonl_file):
        print(f"错误: 输入文件 {jsonl_file} 不存在", file=sys.stderr)
        return
    
    print("=== Duck JSONL to CSV 工具 ===")
    print("用于将JSONL文件转换为CSV文件")
    print("\n")
    
    # 执行转换
    jsonl_to_csv(jsonl_file, csv_file)


if __name__ == "__main__":
    main()