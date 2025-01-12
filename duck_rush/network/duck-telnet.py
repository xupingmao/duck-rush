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
import sys
import traceback
import typing
import logging


class TelnetClient:

    def __init__(self, ip_address: str, port: int):
        self.ip_address = ip_address
        self.port = port
        self.bufsize = 1024

    def run(self):
        socket.setdefaulttimeout(3)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if self.ip_address != "" or self.port != 0:
            self._try_exec(self._connect)

        while True:
            self._try_exec(self._run_loop)
    
    def readuntil(self, ends: bytes):
        buf = b""
        while True:
            tmp_buf = self.sock.recv(self.bufsize)
            if len(tmp_buf) == 0:
                return buf
            buf += tmp_buf
            if buf.endswith(ends):
                return buf
        return buf
    
    def _try_exec(self, func: typing.Callable, *args, **kw):
        try:
            return func(*args, **kw)
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
            traceback.print_exc()

    
    def _connect(self):
        self.sock.connect((self.ip_address, self.port))
        print(f"connect success")

    def _open(self, args: list):
        if len(args) < 2:
            print("Bad args: %s", args)
            return
        
        ip_address = args[0]
        port = int(args[1])

        self.sock.connect((ip_address, port))
    
    def _run_loop(self):
        while True:
            input_str = input("> ")
            command, *args = input_str.split()
            command = command.lower()

            if command == "multi":
                commands = []
                while True:
                    line = input(">> ")
                    if line.lower() in ("end"):
                        break
                    commands.append(line)
                command = "\r\n".join(commands)

            send_str = command + "\r\n"

            if command in ("quit", "exit"):
                print("Bye")
                sys.exit(0)
                break
            elif command == "open":
                self._open(args)
                break
            else:         
                logging.debug("send_str: %r", send_str)
                send_count = self.sock.send(send_str.encode("utf-8"))
                buf = self.readuntil(b"\r\n")
                print(f"recv: {buf}")

def main(ip_address: str, port: str, debug=False):
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    port_int = int(port)
    client = TelnetClient(ip_address=ip_address, port=port_int)
    client.run()

if __name__ == "__main__":
    fire.Fire(main)
