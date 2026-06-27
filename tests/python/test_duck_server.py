#!/usr/bin/env python3
"""单元测试 — duck-server"""

import os
import sys
import json
import time
import socket
import unittest
import tempfile
import threading
import importlib.util
from http.server import HTTPServer

PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
WEB_TOOLS_DIR = os.path.join(PROJECT_ROOT, "duck_rush", "web-tools")
SERVER_PATH = os.path.join(WEB_TOOLS_DIR, "duck-server.py")

spec = importlib.util.spec_from_file_location("duck_server", SERVER_PATH)
assert spec != None
assert spec.loader != None
ds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ds)

Request = ds.Request
BaseBizHandler = ds.BaseBizHandler
DuckRequestHandler = ds.DuckRequestHandler
DuckServer = ds.DuckServer
create_server = ds.create_server
_register_example_routes = ds._register_example_routes
DEFAULT_HOST = ds.DEFAULT_HOST
DEFAULT_PORT = ds.DEFAULT_PORT


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class TestRequest(unittest.TestCase):
    def test_create(self):
        req = Request("/test", {"k": "v"}, b"hello", "GET", {}, ("127.0.0.1", 12345))
        self.assertEqual(req.path, "/test")
        self.assertEqual(req.query, {"k": "v"})
        self.assertEqual(req.body, b"hello")
        self.assertEqual(req.method, "GET")
        self.assertEqual(req.headers, {})
        self.assertEqual(req.client_address, ("127.0.0.1", 12345))

    def test_empty_body(self):
        req = Request("/", {}, b"", "POST", {}, ("::1", 0))
        self.assertEqual(req.body, b"")

    def test_none_body(self):
        req = Request("/path", {"x": "1"}, None, "GET", {}, ("0.0.0.0", 0))
        self.assertIsNone(req.body)

    def test_empty_query(self):
        req = Request("/path", {}, b"", "GET", {}, ("0.0.0.0", 0))
        self.assertEqual(req.query, {})


class TestDuckServer(unittest.TestCase):
    def test_default_host_port(self):
        srv = DuckServer()
        self.assertEqual(srv.host, DEFAULT_HOST)
        self.assertEqual(srv.port, DEFAULT_PORT)

    def test_custom_host_port(self):
        srv = DuckServer(host="127.0.0.1", port=9999)
        self.assertEqual(srv.host, "127.0.0.1")
        self.assertEqual(srv.port, 9999)

    def test_custom_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            srv = DuckServer(directory=tmpdir)
            self.assertEqual(srv.directory, tmpdir)

    def test_default_directory(self):
        srv = DuckServer()
        self.assertEqual(srv.directory, os.getcwd())

    def test_is_running_initially_false(self):
        srv = DuckServer()
        self.assertFalse(srv.is_running)

    def test_get_url(self):
        srv = DuckServer(port=3000)
        self.assertEqual(srv.get_url(), "http://localhost:3000/")

    def test_stop_when_not_running(self):
        srv = DuckServer()
        srv.stop()
        self.assertFalse(srv.is_running)


class TestDuckServerStartStop(unittest.TestCase):
    def setUp(self):
        self.port = _free_port()
        self.srv = DuckServer(port=self.port, host="127.0.0.1")

    def tearDown(self):
        if self.srv.is_running:
            self.srv.stop()

    def test_start_in_thread_and_stop(self):
        thread = self.srv.start_in_thread()
        self.assertIsInstance(thread, threading.Thread)
        for _ in range(20):
            if self.srv.is_running:
                break
            time.sleep(0.01)
        self.assertTrue(self.srv.is_running)
        self.srv.stop()
        self.assertFalse(self.srv.is_running)

    def test_double_stop(self):
        self.srv.start_in_thread()
        time.sleep(0.05)
        self.srv.stop()
        self.srv.stop()
        self.assertFalse(self.srv.is_running)

    def test_start_stop_multiple_times(self):
        thread = self.srv.start_in_thread()
        time.sleep(0.05)
        self.srv.stop()
        self.assertFalse(self.srv.is_running)

        thread2 = self.srv.start_in_thread()
        time.sleep(0.05)
        self.assertTrue(self.srv.is_running)
        self.srv.stop()
        self.assertFalse(self.srv.is_running)


class TestBaseBizHandler(unittest.TestCase):
    def test_init_res_is_none(self):
        h = BaseBizHandler()
        self.assertIsNone(h._res)

    def test_do_GET_raises_without_res(self):
        h = BaseBizHandler()
        req = Request("/", {}, b"", "GET", {}, ("127.0.0.1", 0))
        with self.assertRaises(AttributeError):
            h.do_GET(req)

    def test_do_POST_raises_without_res(self):
        h = BaseBizHandler()
        req = Request("/", {}, b"", "POST", {}, ("127.0.0.1", 0))
        with self.assertRaises(AttributeError):
            h.do_POST(req)

    def test_do_PUT_raises_without_res(self):
        h = BaseBizHandler()
        req = Request("/", {}, b"", "PUT", {}, ("127.0.0.1", 0))
        with self.assertRaises(AttributeError):
            h.do_PUT(req)

    def test_do_DELETE_raises_without_res(self):
        h = BaseBizHandler()
        req = Request("/", {}, b"", "DELETE", {}, ("127.0.0.1", 0))
        with self.assertRaises(AttributeError):
            h.do_DELETE(req)

    def test_get_json_body(self):
        h = BaseBizHandler()
        req = Request("/", {}, b'{"a":1}', "POST", {}, ("127.0.0.1", 0))
        self.assertEqual(h.get_json_body(req), {"a": 1})

    def test_get_json_body_empty(self):
        h = BaseBizHandler()
        req = Request("/", {}, b"", "POST", {}, ("127.0.0.1", 0))
        self.assertIsNone(h.get_json_body(req))

    def test_get_json_body_none(self):
        h = BaseBizHandler()
        req = Request("/", {}, None, "POST", {}, ("127.0.0.1", 0))
        self.assertIsNone(h.get_json_body(req))

    def test_get_json_body_invalid(self):
        h = BaseBizHandler()
        req = Request("/", {}, b"not json", "POST", {}, ("127.0.0.1", 0))
        with self.assertRaises(json.JSONDecodeError):
            h.get_json_body(req)


class TestDuckRequestHandlerClassVars(unittest.TestCase):
    def setUp(self):
        self._saved_routes = DuckRequestHandler.CUSTOM_ROUTES.copy()
        self._saved_origins = DuckRequestHandler.CORS_ORIGINS.copy()

    def tearDown(self):
        DuckRequestHandler.CUSTOM_ROUTES = self._saved_routes
        DuckRequestHandler.CORS_ORIGINS = self._saved_origins

    def test_default_cors_origins(self):
        self.assertEqual(DuckRequestHandler.CORS_ORIGINS, ["*"])

    def test_default_custom_routes(self):
        self.assertIsInstance(DuckRequestHandler.CUSTOM_ROUTES, dict)

    def test_register_and_reset_routes(self):
        class Dummy(BaseBizHandler):
            def do_GET(self, request):
                return {"ok": True}

        DuckRequestHandler.CUSTOM_ROUTES = {"/api/dummy": Dummy}
        self.assertIn("/api/dummy", DuckRequestHandler.CUSTOM_ROUTES)
        self.assertIs(DuckRequestHandler.CUSTOM_ROUTES["/api/dummy"], Dummy)

    def test_cors_origins_custom(self):
        DuckRequestHandler.CORS_ORIGINS = ["http://localhost:3000"]
        self.assertEqual(
            DuckRequestHandler.CORS_ORIGINS,
            ["http://localhost:3000"],
        )


class TestExampleRoutes(unittest.TestCase):
    def setUp(self):
        self._saved_routes = DuckRequestHandler.CUSTOM_ROUTES.copy()

    def tearDown(self):
        DuckRequestHandler.CUSTOM_ROUTES = self._saved_routes

    def test_register_example_routes(self):
        _register_example_routes()
        self.assertIn("/api/status", DuckRequestHandler.CUSTOM_ROUTES)
        self.assertIn("/api/info", DuckRequestHandler.CUSTOM_ROUTES)

    def test_status_handler_returns_dict(self):
        _register_example_routes()
        handler_cls = DuckRequestHandler.CUSTOM_ROUTES["/api/status"]
        handler = handler_cls()
        req = Request("/api/status", {}, b"", "GET", {}, ("127.0.0.1", 0))
        result = handler.do_GET(req)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("status"), "ok")
        self.assertIn("time", result)
        self.assertIn("version", result)

    def test_status_handler_post(self):
        _register_example_routes()
        handler_cls = DuckRequestHandler.CUSTOM_ROUTES["/api/status"]
        handler = handler_cls()
        req = Request("/api/status", {}, b'{"foo":"bar"}', "POST", {}, ("127.0.0.1", 0))
        result = handler.do_POST(req)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("method"), "POST")
        self.assertEqual(result.get("received"), {"foo": "bar"})

    def test_info_handler_returns_dict(self):
        _register_example_routes()
        handler_cls = DuckRequestHandler.CUSTOM_ROUTES["/api/info"]
        handler = handler_cls()
        req = Request("/api/info", {}, b"", "GET", {}, ("127.0.0.1", 0))
        result = handler.do_GET(req)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("name"), "Duck Server")


class TestCreateServer(unittest.TestCase):
    def test_create_defaults(self):
        srv = create_server()
        self.assertIsInstance(srv, DuckServer)
        self.assertEqual(srv.host, DEFAULT_HOST)
        self.assertEqual(srv.port, DEFAULT_PORT)

    def test_create_with_args(self):
        srv = create_server(host="127.0.0.1", port=8080, directory="/tmp")
        self.assertEqual(srv.host, "127.0.0.1")
        self.assertEqual(srv.port, 8080)
        self.assertEqual(srv.directory, "/tmp")

    def test_create_server_is_duck_server(self):
        srv = create_server()
        self.assertIsInstance(srv, DuckServer)


class TestHandleCustomRoute(unittest.TestCase):
    def test_no_route_found(self):
        DummyHandler = type("DummyHandler", (DuckRequestHandler,), {})
        instance = DummyHandler.__new__(DummyHandler)
        instance.path = "/not-registered"
        instance.headers = {}
        instance.client_address = ("127.0.0.1", 0)
        instance.command = "GET"
        result = DuckRequestHandler.handle_custom_route(instance, "GET")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
