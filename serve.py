#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ETF 对比页 本地静态服务 + 东财行情代理（免跨域）
用法:  python serve.py [端口]   默认 8937
打开 http://127.0.0.1:8937/ 即可，行情/净值走本服务转发，无 CORS。
"""
import gzip
import json
import sys
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8937
ROOT = Path(__file__).resolve().parent

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
}


def fetch_em(url, referer):
    """请求东财，带浏览器 UA/Referer，处理 gzip。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": referer,
        "Accept": "*/*",
        "Accept-Encoding": "gzip",
    })
    with urllib.request.urlopen(req, timeout=12) as resp:
        raw = resp.read()
        if (resp.headers.get("Content-Encoding") or "").lower() == "gzip":
            raw = gzip.decompress(raw)
        return raw


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    # ---- 路由 ----
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path == "/api/quote":
                self.api_quote(u)
            elif u.path == "/api/nav":
                self.api_nav(u)
            else:
                self.serve_static(u.path)
        except Exception as ex:  # noqa: BLE001
            self.send_json({"error": str(ex)}, 502)

    # ---- 行情（实时价/涨跌/最高最低等）----
    def api_quote(self, u):
        q = urllib.parse.parse_qs(u.query)
        secids = (q.get("secids") or [""])[0]
        fields = (q.get("fields") or [""])[0]
        if not secids:
            self.send_json({"error": "missing secids"}, 400)
            return
        url = ("https://push2delay.eastmoney.com/api/qt/ulist.np/get"
               "?fltt=2&fields=" + urllib.parse.quote(fields) +
               "&secids=" + urllib.parse.quote(secids))
        body = fetch_em(url, "https://quote.eastmoney.com/")
        self.send_bytes(body, "application/json")

    # ---- 单位净值（QDII T+1）----
    def api_nav(self, u):
        q = urllib.parse.parse_qs(u.query)
        code = (q.get("fundCode") or [""])[0]
        page_index = (q.get("pageIndex") or ["1"])[0]
        page_size = (q.get("pageSize") or ["3"])[0]
        if not code:
            self.send_json({"error": "missing fundCode"}, 400)
            return
        url = ("https://api.fund.eastmoney.com/f10/lsjz?fundCode=" +
               urllib.parse.quote(code) + "&pageIndex=" + page_index +
               "&pageSize=" + page_size)
        body = fetch_em(url, "https://fundf10.eastmoney.com/")
        self.send_bytes(body, "application/json")

    # ---- 静态文件 ----
    def serve_static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        rel = path.lstrip("/")
        f = ROOT / rel
        try:
            f.resolve().relative_to(ROOT.resolve())
        except ValueError:
            self.send_json({"error": "forbidden"}, 403)
            return
        if not f.is_file():
            self.send_json({"error": "not found"}, 404)
            return
        ctype = CONTENT_TYPES.get(f.suffix.lower(), "application/octet-stream")
        data = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    # ---- 响应辅助 ----
    def send_bytes(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("ETF 对比页 + 东财代理已启动: http://127.0.0.1:%d/  (Ctrl+C 退出)" % PORT, flush=True)
    srv.serve_forever()
