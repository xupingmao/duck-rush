# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2024-07-20 11:09:46
LastEditors: xupingmao
LastEditTime: 2024-07-20 11:23:31
FilePath: /duck_rush/duck_rush/network/duck-telnet.py
Description: 描述
'''

import socket
import fire

def check_tcp_port(ip_address: str, port: str):
    port_int = int(port)
    socket.setdefaulttimeout(3)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((ip_address, port_int))
        print(f"connect success")
    except socket.timeout:
        print("connect timeout")
    except ConnectionRefusedError:
        print("connect refused")
    except TimeoutError:
        print("connect timeout")
    except InterruptedError:
        print("connect interrupted")
    except Exception as e:
        print("unknown exception")
        raise e

if __name__ == "__main__":
    fire.Fire(check_tcp_port)
