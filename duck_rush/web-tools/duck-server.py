#!/usr/bin/env python3
"""
Duck HTTP Server - 基于 http.server 的可扩展 Web 服务器
提供 CORS 支持、请求日志、静态文件服务等基础功能，方便后续扩展。

Usage:
    python duck-server.py              # 启动服务器（默认端口 8000）
    python duck-server.py --port 3000  # 指定端口
    python duck-server.py --help       # 显示帮助信息
"""

import os
import sys
import json
import time
import logging
import argparse
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ──────────────────────────────────────────────
#  配置
# ──────────────────────────────────────────────
DEFAULT_PORT = 8000
DEFAULT_HOST = "0.0.0.0"

# ──────────────────────────────────────────────
#  日志
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("duck-server")


class Request:
    """封装请求信息，供 RouteHandler 使用"""

    def __init__(self, handler, path, query, body):
        self._handler = handler
        self.path = path
        self.query = query
        self.body = body
        self.method = handler.command
        self.headers = handler.headers
        self.client_address = handler.client_address

    def send_json(self, data, status=200):
        self._handler.send_json(data, status)

    def send_text(self, text, status=200, content_type="text/plain; charset=utf-8"):
        self._handler.send_text(text, status, content_type)

    def send_error(self, code, message=None):
        self._handler.send_error(code, message)

    def get_json_body(self):
        return json.loads(self.body) if self.body else None


class RouteHandler:
    """路由处理器的基类，子类实现 do_GET / do_POST 等方法"""

    def do_GET(self, request):
        self._method_not_allowed(request)

    def do_POST(self, request):
        self._method_not_allowed(request)

    def do_PUT(self, request):
        self._method_not_allowed(request)

    def do_DELETE(self, request):
        self._method_not_allowed(request)

    def _method_not_allowed(self, request):
        request.send_error(405, "Method Not Allowed")


class DuckRequestHandler(SimpleHTTPRequestHandler):
    """可扩展的 HTTP 请求处理器"""

    # 允许跨域的域名列表（空列表表示不限制）
    CORS_ORIGINS = ["*"]

    # 自定义路由表：{path: handler_class}
    # handler_class 是 RouteHandler 的子类，含 do_GET/do_POST 等方法
    CUSTOM_ROUTES = {}

    def do_OPTIONS(self):
        self.send_cors_headers()
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.handle_custom_route("GET"):
            return
        super().do_GET()

    def do_POST(self):
        if self.handle_custom_route("POST"):
            return
        self.send_error(405, "Method Not Allowed")

    def do_PUT(self):
        if self.handle_custom_route("PUT"):
            return
        self.send_error(405, "Method Not Allowed")

    def do_DELETE(self):
        if self.handle_custom_route("DELETE"):
            return
        self.send_error(405, "Method Not Allowed")

    # ── CORS ──────────────────────────────────

    def send_cors_headers(self):
        origins = self.CORS_ORIGINS
        if origins and len(origins) > 0:
            origin = origins[0] if origins != ["*"] else "*"
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Max-Age", "86400")

    def end_headers(self):
        self.send_cors_headers()
        super().end_headers()

    # ── 自定义路由 ────────────────────────────

    def handle_custom_route(self, method):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = dict((k, v[0]) for k, v in parse_qs(parsed.query).items())

        handler_class = self.CUSTOM_ROUTES.get(path)
        if handler_class is None:
            return False

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        try:
            handler = handler_class()
            req = Request(self, path, query, body)
            method_handler = getattr(handler, f"do_{method}", None)
            if method_handler is None:
                handler._method_not_allowed(req)
                return True
            result = method_handler(req)
            if result is None:
                return True
            if isinstance(result, dict):
                self.send_json(result)
            else:
                self.send_text(str(result))
        except Exception as e:
            log.error(f"路由处理错误: {e}")
            self.send_error(500, f"Internal Server Error: {e}")
        return True

    # ── 响应辅助 ──────────────────────────────

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text, status=200, content_type="text/plain; charset=utf-8"):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── 日志 ──────────────────────────────────

    def log_message(self, format, *args):
        log.info(f"{self.client_address[0]} - {format % args}")


class DuckServer:
    """封装 HTTPServer，提供 start / stop 接口"""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, directory=None):
        self.host = host
        self.port = port
        self.directory = directory or os.getcwd()
        self._server = None
        self._thread = None

    def start(self):
        os.chdir(self.directory)
        self._server = HTTPServer((self.host, self.port), DuckRequestHandler)
        log.info(f"服务器已启动: http://localhost:{self.port}/")
        log.info(f"服务目录: {self.directory}")
        self._server.serve_forever()

    def start_in_thread(self):
        self._thread = threading.Thread(target=self.start, daemon=True)
        self._thread.start()
        log.info(f"服务器已在后台线程启动 (端口 {self.port})")
        return self._thread

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            log.info("服务器已停止")

    @property
    def is_running(self):
        return self._server is not None

    def get_url(self):
        return f"http://localhost:{self.port}/"


def create_server(host=DEFAULT_HOST, port=DEFAULT_PORT, directory=None):
    """快捷创建 DuckServer 实例"""
    return DuckServer(host=host, port=port, directory=directory)


# ── 注册自定义路由示例 ────────────────────────
class _StatusHandler(RouteHandler):
    def do_GET(self, request):
        return {"status": "ok", "time": time.time(), "version": "1.0"}

    def do_POST(self, request):
        data = request.get_json_body()
        return {"received": data, "method": "POST"}


class _InfoHandler(RouteHandler):
    def do_GET(self, request):
        return {
            "name": "Duck Server",
            "description": "基于 http.server 的可扩展 Web 服务器",
        }


def _register_example_routes():
    DuckRequestHandler.CUSTOM_ROUTES = {
        "/api/status": _StatusHandler,
        "/api/info": _InfoHandler,
    }


# ── 命令行入口 ────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Duck HTTP Server")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT, help=f"端口号 (默认: {DEFAULT_PORT})")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help=f"监听地址 (默认: {DEFAULT_HOST})")
    parser.add_argument("--directory", "-d", type=str, default=None, help="服务目录 (默认: 当前目录)")
    parser.add_argument("--example-routes", action="store_true", help="注册示例 API 路由")
    args = parser.parse_args()

    if args.example_routes:
        _register_example_routes()

    server = DuckServer(
        host=args.host,
        port=args.port,
        directory=args.directory,
    )

    try:
        server.start()
    except KeyboardInterrupt:
        print()
        log.info("正在停止服务器...")
        server.stop()


if __name__ == "__main__":
    main()
