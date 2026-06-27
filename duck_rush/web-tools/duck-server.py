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
from email.message import Message
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ──────────────────────────────────────────────
#  配置
# ──────────────────────────────────────────────
DEFAULT_PORT: int = 8000
DEFAULT_HOST: str = "0.0.0.0"

class ServerConfig:
    debug_log = False

# ──────────────────────────────────────────────
#  日志
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log: logging.Logger = logging.getLogger("duck-server")


class Request:
    """纯数据对象 — 承载请求输入，不含响应方法"""

    path: str
    query: Dict[str, str]
    body: bytes
    method: str
    headers: Message
    client_address: Tuple[str, int]

    def __init__(
        self,
        path: str,
        query: Dict[str, str],
        body: bytes,
        method: str,
        headers: Message,
        client_address: Tuple[str, int],
    ) -> None:
        self.path = path
        self.query = query
        self.body = body
        self.method = method
        self.headers = headers
        self.client_address = client_address


class BaseBizHandler:
    """业务处理器基类 — 通过 self.send_*() 输出响应，request 参数为输入"""

    _res: 'DuckRequestHandler'

    def __init__(self) -> None:
        self._res = None  # type: ignore[assignment]

    def do_GET(self, request: Request) -> Any:
        self.send_error(405)

    def do_POST(self, request: Request) -> Any:
        self.send_error(405)

    def do_PUT(self, request: Request) -> Any:
        self.send_error(405)

    def do_DELETE(self, request: Request) -> Any:
        self.send_error(405)

    def send_json(self, data: Any, status: int = 200) -> None:
        self._res.send_json(data, status)

    def send_text(
        self,
        text: str,
        status: int = 200,
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        self._res.send_text(text, status, content_type)

    def send_error(self, code: int, message: Optional[str] = None) -> None:
        self._res.send_error(code, message)

    def get_json_body(self, request: Request) -> Any:
        return json.loads(request.body) if request.body else None


class DuckRequestHandler(SimpleHTTPRequestHandler):
    """HTTP 请求处理器 — 静态文件服务 + 自定义路由分发"""

    CORS_ORIGINS: ClassVar[List[str]] = ["*"]

    # 需要指定 charset=utf-8 的文本文件扩展名
    _TEXT_EXTENSIONS: ClassVar[set] = {
        ".js", ".css", ".html", ".htm", ".json", ".svg",
        ".xml", ".txt", ".md", ".mjs", ".cjs", ".vue",
    }

    def guess_type(self, path) -> str:
        ctype = super().guess_type(path)
        if ctype and ctype.startswith("text/"):
            return ctype + "; charset=utf-8"
        if ctype == "application/javascript":
            return "application/javascript; charset=utf-8"
        ext = os.path.splitext(path)[1].lower()
        if ext in self._TEXT_EXTENSIONS:
            return f"{ctype or 'application/octet-stream'}; charset=utf-8"
        return ctype or "application/octet-stream"

    # 自定义路由表：{path: BaseBizHandler 子类}
    CUSTOM_ROUTES: ClassVar[Dict[str, Type[BaseBizHandler]]] = {}

    # ── HTTP 方法 ─────────────────────────────

    def do_OPTIONS(self) -> None:
        self.send_cors_headers()
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        if self.handle_custom_route("GET"):
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.handle_custom_route("POST"):
            return
        self.send_error(405, "Method Not Allowed")

    def do_PUT(self) -> None:
        if self.handle_custom_route("PUT"):
            return
        self.send_error(405, "Method Not Allowed")

    def do_DELETE(self) -> None:
        if self.handle_custom_route("DELETE"):
            return
        self.send_error(405, "Method Not Allowed")

    # ── CORS ──────────────────────────────────

    def send_cors_headers(self) -> None:
        origins = self.CORS_ORIGINS
        if origins and len(origins) > 0:
            origin = origins[0] if origins != ["*"] else "*"
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Max-Age", "86400")

    def end_headers(self) -> None:
        self.send_cors_headers()
        super().end_headers()

    # ── 自定义路由 ────────────────────────────

    def handle_custom_route(self, method: str) -> bool:
        parsed = urlparse(self.path)
        path: str = parsed.path.rstrip("/") or "/"
        query: Dict[str, str] = dict(
            (k, v[0]) for k, v in parse_qs(parsed.query).items()
        )
        
        if ServerConfig.debug_log:
            log.debug("path = %s", path)

        handler_class: Optional[Type[BaseBizHandler]] = self.CUSTOM_ROUTES.get(path)
        if handler_class is None:
            return False

        content_length: int = int(self.headers.get("Content-Length", 0))
        body: bytes = self.rfile.read(content_length) if content_length > 0 else b""

        try:
            handler: BaseBizHandler = handler_class()
            handler._res = self
            req = Request(path, query, body, method, self.headers, self.client_address)
            fn = getattr(handler, f"do_{method}", None)
            if fn is None:
                handler.send_error(405)
                return True
            result: Any = fn(req)
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

    def send_json(self, data: Any, status: int = 200) -> None:
        body: bytes = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(
        self,
        text: str,
        status: int = 200,
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        body: bytes = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── 日志 ──────────────────────────────────

    def log_message(self, format: str, *args: Any) -> None:
        log.info(f"{self.client_address[0]} - {format % args}")


class DuckServer:
    """封装 HTTPServer，提供 start / stop 接口"""

    host: str
    port: int
    directory: str
    _server: Optional[HTTPServer]
    _thread: Optional[threading.Thread]

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        directory: Optional[str] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.directory = directory or os.getcwd()
        self._server = None
        self._thread = None

    def start(self) -> None:
        os.chdir(self.directory)
        self._server = HTTPServer((self.host, self.port), DuckRequestHandler)
        log.info(f"服务器已启动: http://localhost:{self.port}/")
        log.info(f"服务目录: {self.directory}")
        self._server.serve_forever()

    def start_in_thread(self) -> threading.Thread:
        self._thread = threading.Thread(target=self.start, daemon=True)
        self._thread.start()
        log.info(f"服务器已在后台线程启动 (端口 {self.port})")
        return self._thread

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            log.info("服务器已停止")

    @property
    def is_running(self) -> bool:
        return self._server is not None

    def get_url(self) -> str:
        return f"http://localhost:{self.port}/"


def create_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    directory: Optional[str] = None,
) -> DuckServer:
    """快捷创建 DuckServer 实例"""
    return DuckServer(host=host, port=port, directory=directory)


# ── 注册自定义路由示例 ────────────────────────
class _StatusHandler(BaseBizHandler):
    def do_GET(self, request: Request) -> Dict[str, Any]:
        return {"status": "ok", "time": time.time(), "version": "1.0"}

    def do_POST(self, request: Request) -> Dict[str, Any]:
        data = self.get_json_body(request)
        return {"received": data, "method": "POST"}


class _InfoHandler(BaseBizHandler):
    def do_GET(self, request: Request) -> Dict[str, str]:
        return {
            "name": "Duck Server",
            "description": "基于 http.server 的可扩展 Web 服务器",
        }


class _ShellHandler(BaseBizHandler):
    """处理 Shell 文本处理命令 — 将输入文本通过管道传给指定命令"""

    ALLOWED_COMMANDS: List[str] = [
        "grep", "sort", "uniq", "head", "tail", "sed", "awk", "wc",
        "cut", "tr", "rev", "cat", "tac", "nl", "fmt", "pr", "fold",
        "paste", "join", "comm", "diff", "expand", "unexpand",
    ]

    def _check_command(self, cmd: str) -> str:
        """安全检查：只允许已知命令和管道操作"""
        import re
        # 允许字母数字、空格、/、-、_、.、'、"、$、|、>、<、;
        if not re.match(r'^[a-zA-Z0-9\s/\-_.\'\"$^{}()\[\]|><;]+$', cmd):
            raise ValueError("命令包含不允许的字符")
        # 按管道拆分，逐个检查每个命令
        segments = cmd.split("|")
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            first_word = seg.split()[0] if seg else ""
            base = os.path.basename(first_word)
            if base not in self.ALLOWED_COMMANDS:
                raise ValueError(f"命令 \"{base}\" 不在允许列表中")
        return cmd

    def do_POST(self, request: Request) -> Dict[str, Any]:
        import subprocess
        data = self.get_json_body(request)
        if not data:
            return {"error": "请求体为空"}

        text = data.get("text", "")
        command = data.get("command", "")
        
        if ServerConfig.debug_log:
            log.debug("command = %s", command)

        if not text:
            return {"error": "输入文本为空"}
        if not command:
            return {"error": "命令为空"}

        try:
            command = self._check_command(command)
        except ValueError as e:
            return {"error": str(e)}

        try:
            proc = subprocess.run(
                command,
                shell=True,
                input=text,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "output": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "命令执行超时"}
        except Exception as e:
            return {"error": f"执行失败: {e}"}


def _register_core_routes() -> None:
    DuckRequestHandler.CUSTOM_ROUTES.update({
        "/api/run-shell": _ShellHandler,
    })


def _register_example_routes() -> None:
    DuckRequestHandler.CUSTOM_ROUTES.update({
        "/api/status": _StatusHandler,
        "/api/info": _InfoHandler,
    })


# ── 命令行入口 ────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="Duck HTTP Server")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT, help=f"端口号 (默认: {DEFAULT_PORT})")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help=f"监听地址 (默认: {DEFAULT_HOST})")
    parser.add_argument("--directory", "-d", type=str, default=None, help="服务目录 (默认: 当前目录)")
    parser.add_argument("--example-routes", action="store_true", help="注册示例 API 路由")
    parser.add_argument("--debug-log", action="store_true", help="开启调试日志")
    args = parser.parse_args()

    _register_core_routes()
    if args.example_routes:
        _register_example_routes()
        
    ServerConfig.debug_log = args.debug_log
    if args.debug_log:
        logging.getLogger().setLevel(logging.DEBUG)

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
