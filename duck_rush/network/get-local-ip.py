# encoding=utf-8
import fire
import os
import platform
import socket
import json


def get_local_ip_by_socket():
    """使用UDP协议获取当前的局域网地址
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("128.0.0.1", 80)) # 随便一个有效的IP地址即可, 但是不能是127.0.0.1
        ip, port = s.getsockname()
        return ip

def format_line(field, value):
    return "%-20s%-20s\n" % (field, value)

def main():
    result = {
        "os.name": os.name,
        "platform.system": platform.system(),
        "local_ip": get_local_ip_by_socket()
    }
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    fire.Fire(main)