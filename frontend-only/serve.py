#!/usr/bin/env python
# 苹果检测 · 本地静态服务器（零依赖，仅用 Python 标准库）
# 双击同目录的「本地运行.bat」即可启动并自动打开浏览器。
import http.server
import socketserver
import webbrowser
import socket
import os
import sys

# 强制 MIME 映射：.mjs 必须是 JS 类型，否则浏览器拒绝执行 ES 模块；
# .wasm 必须是 application/wasm，否则无法实例化 WebAssembly
_MIME_OVERRIDE = {
    ".wasm": "application/wasm",
    ".mjs": "text/javascript",
    ".js": "text/javascript",
    ".onnx": "application/octet-stream",
}

HOST = "127.0.0.1"  # 仅本机访问，不对外暴露


def find_free_port(start=8080):
    p = start
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((HOST, p)) != 0:
                return p
        p += 1


class Handler(http.server.SimpleHTTPRequestHandler):
    def _force_ctype(self, path):
        ext = os.path.splitext(path)[1].lower()
        return _MIME_OVERRIDE.get(ext)

    def guess_response_type(self, path, content=None):
        forced = self._force_ctype(path)
        if forced:
            return [(forced, {})]
        return super().guess_response_type(path, content=content)

    def guess_type(self, path):
        forced = self._force_ctype(path)
        if forced:
            return forced
        return super().guess_type(path)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # 静默日志，避免刷屏


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    PORT = find_free_port(8080)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((HOST, PORT), Handler) as httpd:
        url = f"http://{HOST}:{PORT}/"
        print("=" * 50)
        print("  苹果检测（纯前端）本地服务已启动")
        print(f"  请在浏览器打开：{url}")
        print("  按 Ctrl+C 停止服务")
        print("=" * 50)
        try:
            webbrowser.open(url)
        except Exception:
            pass  # 无图形界面时忽略，手动复制上面的地址打开即可
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止。")
            sys.exit(0)
