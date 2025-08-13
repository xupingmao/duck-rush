import struct
import base64


def encode_base32(data: bytes) -> str:
    encoded = base64.b32hexencode(data).decode('ascii')
    return encoded.rstrip('=')  # 移除填充字符

def decode_base32(encoded: str) -> bytes:
    # 添加缺失的填充字符
    padding = '=' * ((8 - len(encoded) % 8) % 8)
    return base64.b32hexdecode(encoded + padding)

def encode_int64(value: int) -> str:
    """将int64有符号整数编码为保持顺序的字符串"""
    # 将数值转换为8字节大端序字节流
    if value < 0:
        # 负数处理：取反加1转换为正数表示，并添加前缀'a'
        # 使用补码表示法
        value_str = encode_base32(struct.pack('>q', value))
        encoded_str = '0' + value_str
    else:
        # 正数处理：直接编码，并添加前缀'b'
        value_str = encode_base32(struct.pack('>q', value))
        encoded_str = '1' + value_str
    
    return encoded_str

def decode_int64(encoded_str: str) -> int:
    """将编码后的字符串解码为int64有符号整数"""
    
    # 根据前缀判断正负
    prefix = encoded_str[0:1]
    value_str = encoded_str[1:]

    value_bytes = decode_base32(value_str)

    if prefix == '0':
        # 负数
        value = struct.unpack('>q', value_bytes)[0]
    elif prefix == '1':
        # 正数
        value = struct.unpack('>q', value_bytes)[0]
    else:
        raise ValueError("Invalid encoded string prefix")
    
    return value


# 示例用法
if __name__ == "__main__":
    test_values = [0, 1, -1, 2**63-1, -2**63, 3567]

    test_values = sorted(test_values)
    print("test_values", test_values)
    
    for value in test_values:
        print(f"原始值: {value}")
        encoded = encode_int64(value)
        print(f"编码后: {encoded}")
        decoded = decode_int64(encoded)
        print(f"解码后: {decoded}")
        print("---")
        assert decoded == value

    encode_values = sorted([encode_int64(v) for v in test_values])
    decode_values = [decode_int64(v) for v in encode_values]

    print("encode_values", encode_values)
    print("decode_values", decode_values)

    assert decode_values == test_values