# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2026/09/10
# @filename duck-http.py
# @description 命令行 HTTP 客户端（curl 风格，基于标准库 urllib）
"""duck-http —— 命令行 HTTP 客户端，用于发请求、看响应头、下载文件。

用法:
  duck-http <URL> [选项]

选项:
  -X, --method METHOD   请求方法（默认 GET，带 -d/--data 时默认 POST）
  -H, --header "K: V"   请求头，可重复指定
  -d, --data DATA       请求体，如 "a=1&b=2"
  --json TEXT           请求体（自动设置 Content-Type: application/json）
  -o, --output FILE     把响应体写入文件（下载）
  -i, --include         同时输出响应头
  -I, --head-only       只输出响应头（HEAD 请求）
  -t, --timeout SEC     超时秒数（默认 30）
  --pretty              响应是 JSON 时格式化输出
  -A, --user-agent UA   自定义 User-Agent
  -h, --help            显示本帮助

示例:
  duck-http https://api.github.com --pretty
  duck-http https://httpbin.org/post -X POST -d "a=1"
  duck-http https://example.com/a.zip -o a.zip
  duck-http https://example.com -I
"""

import sys
import json
import argparse
import urllib.request
import urllib.error
from typing import List, Optional, Tuple

DEFAULT_TIMEOUT = 30
DEFAULT_UA = "duck-http/1.0"


def build_headers(header_list: List[str], user_agent: str,
                  body: Optional[bytes], use_json: bool) -> dict:
    """把命令行参数组装成请求头字典"""
    headers = {"User-Agent": user_agent}
    if body is not None:
        if use_json:
            headers["Content-Type"] = "application/json; charset=utf-8"
        else:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
    for item in header_list:
        if ":" not in item:
            print("忽略格式错误的请求头: %s" % item, file=sys.stderr)
            continue
        key, value = item.split(":", 1)
        headers[key.strip()] = value.strip()
    return headers


def resolve_method(method: Optional[str], body: Optional[bytes],
                   head_only: bool) -> str:
    """确定请求方法"""
    if head_only:
        return "HEAD"
    if method:
        return method.upper()
    if body is not None:
        return "POST"
    return "GET"


def request(url: str, method: str, headers: dict, body: Optional[bytes],
            timeout: float) -> Tuple[int, dict, bytes]:
    """发起请求, 返回 (状态码, 响应头字典, 响应体)"""
    req = urllib.request.Request(url, data=body, headers=headers,
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()
    except urllib.error.HTTPError as e:
        # 4xx/5xx 也会带上响应体, 一并读出方便排查
        return e.code, dict(e.headers.items()), e.read()


def decode_body(raw: bytes, resp_headers: dict) -> str:
    """按响应头声明的字符集解码响应体"""
    content_type = resp_headers.get("Content-Type", "")
    encoding = "utf-8"
    if "charset=" in content_type:
        encoding = content_type.split("charset=")[-1].split(";")[0].strip()
    return raw.decode(encoding, errors="replace")


def format_status_line(status: int, resp_headers: dict) -> str:
    return "HTTP/1.1 %d %s" % (status, resp_headers.get("Status", ""))


def try_pretty(text: str) -> str:
    """JSON 响应尝试格式化输出, 解析失败则原样返回"""
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except ValueError:
        return text


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="命令行 HTTP 客户端")
    parser.add_argument("url", help="请求的 URL")
    parser.add_argument("-X", "--method", default=None, help="请求方法")
    parser.add_argument("-H", "--header", action="append", default=[],
                        help='请求头, 如 "Authorization: Bearer xxx"，可重复指定')
    parser.add_argument("-d", "--data", default=None, help="请求体")
    parser.add_argument("--json", default=None, help="JSON 格式的请求体")
    parser.add_argument("-o", "--output", default=None, help="把响应体写入文件")
    parser.add_argument("-i", "--include", action="store_true",
                        help="同时输出响应头")
    parser.add_argument("-I", "--head-only", action="store_true",
                        help="只输出响应头")
    parser.add_argument("-t", "--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help="超时秒数（默认 30）")
    parser.add_argument("--pretty", action="store_true",
                        help="响应是 JSON 时格式化输出")
    parser.add_argument("-A", "--user-agent", default=DEFAULT_UA,
                        help="自定义 User-Agent")
    args = parser.parse_args(argv)

    body: Optional[bytes] = None
    if args.json is not None:
        body = args.json.encode("utf-8")
    elif args.data is not None:
        body = args.data.encode("utf-8")

    use_json = args.json is not None
    headers = build_headers(args.header, args.user_agent, body, use_json)
    method = resolve_method(args.method, body, args.head_only)

    try:
        status, resp_headers, raw = request(
            args.url, method, headers, body, args.timeout)
    except urllib.error.URLError as e:
        print("请求失败: %s (%s)" % (args.url, e.reason), file=sys.stderr)
        return 1
    except OSError as e:
        print("请求失败: %s (%s)" % (args.url, e), file=sys.stderr)
        return 1

    if args.output:
        with open(args.output, "wb") as fp:
            fp.write(raw)
        print("已保存 %d 字节 -> %s (HTTP %d)" % (len(raw), args.output, status))
        return 0 if status < 400 else 1

    if args.include or args.head_only:
        print(format_status_line(status, resp_headers))
        for key, value in resp_headers.items():
            print("%s: %s" % (key, value))
        print("")

    if args.head_only:
        return 0 if status < 400 else 1

    text = decode_body(raw, resp_headers)
    if args.pretty:
        text = try_pretty(text)
    print(text)

    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
