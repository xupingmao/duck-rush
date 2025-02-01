# encoding=utf-8

import fire
from socket import socket, AF_INET, SOCK_STREAM

class ScanConfig:
    timeout = 1.0

def clean_line():
    print("\033[2K\033[1G", end="", flush=True)


#list_sort = sorted(list, key = lambda d:d[0], reverse = False)
def check_net_addr(host="127.0.0.1", port=80):
    clean_line()
    print(f"checking {host}:{port}", end="", flush=True)

    try:
        tcpCliSock = socket(AF_INET,SOCK_STREAM)
        tcpCliSock.settimeout(ScanConfig.timeout)
        tcpCliSock.connect((host,port))
        tcpCliSock.close()
        del tcpCliSock
        clean_line()
        print(f"{host}:{port} -> open")
        # fileobject.writelines([result])
    except Exception as error:
        pass

def scan(prefix="", next=[], port=80):
    if len(next) == 0:
        check_net_addr(host=prefix, port=port)
    else:
        if prefix != "":
            prefix += "."
        
        part, rest = next[0], next[1:]
        if part == "*":
            for x in range(256):
                scan(prefix=f"{prefix}{x}", next=rest, port=port)
        else:
            scan(prefix=f"{prefix}{part}", next=rest, port=port)

def main(ip="127.0.0.*", port=80, timeout=1.0):
    ScanConfig.timeout = timeout
    parts = ip.split(".")
    return scan(prefix="", next=parts, port=port)



if __name__ == "__main__":
    fire.Fire(main)