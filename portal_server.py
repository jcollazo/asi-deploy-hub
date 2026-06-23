#!/usr/bin/env python3
"""FBIB Portal Server — static frontend on port 80 with /api proxy to :8900"""
import http.server
import urllib.request
import os
import sys

DIST = "/opt/data/asi-deploy-hub/frontend/dist"
API_HOST = "http://127.0.0.1:8900"
PORT = 80

class PortalHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            # SPA fallback — serve index.html for non-file routes
            filepath = os.path.join(DIST, self.path.lstrip("/"))
            if not os.path.exists(filepath) or not os.path.isfile(filepath):
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            self.send_error(404)

    def do_PUT(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            self.send_error(404)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            self.send_error(404)

    def _proxy(self):
        try:
            url = f"{API_HOST}{self.path}"
            body = None
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                body = self.rfile.read(content_length)

            req = urllib.request.Request(url, data=body, method=self.command)
            # Forward relevant headers
            for h in ["Content-Type", "Authorization"]:
                if h in self.headers:
                    req.add_header(h, self.headers[h])

            with urllib.request.urlopen(req, timeout=30) as resp:
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_error(502, f"API Error: {e}")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[FBIB] {args[0]}")

if __name__ == "__main__":
    os.chdir(DIST)
    server = http.server.HTTPServer(("0.0.0.0", PORT), PortalHandler)
    print(f"🚀 FBIB Portal → http://0.0.0.0:{PORT}")
    print(f"   Static: {DIST}")
    print(f"   API proxy → {API_HOST}")
    server.serve_forever()
