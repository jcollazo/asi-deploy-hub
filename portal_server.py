#!/usr/bin/env python3
"""FBIB Portal Server — HTTP :80 + HTTPS :443 (one server, two ports)"""
import http.server
import urllib.request
import ssl
import os
import sys
import threading
import subprocess

DIST = "/opt/data/asi-deploy-hub/frontend/dist"
API_HOST = "http://127.0.0.1:8900"

CERT = "/tmp/selfsigned.crt"
KEY = "/tmp/selfsigned.key"

# Generate self-signed cert if missing
if not os.path.exists(CERT):
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", KEY, "-out", CERT, "-days", "365", "-nodes",
        "-subj", f"/CN={os.environ.get('TRAEFIK_HOST', 'fbib')}"
    ], check=True, capture_output=True)

class PortalHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            filepath = os.path.join(DIST, self.path.lstrip("/"))
            if not os.path.exists(filepath) or not os.path.isfile(filepath):
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"): self._proxy()
        else: self.send_error(404)

    def do_PUT(self):
        if self.path.startswith("/api/"): self._proxy()
        else: self.send_error(404)

    def do_DELETE(self):
        if self.path.startswith("/api/"): self._proxy()
        else: self.send_error(404)

    def _proxy(self):
        try:
            url = f"{API_HOST}{self.path}"
            body = None
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                body = self.rfile.read(content_length)
            req = urllib.request.Request(url, data=body, method=self.command)
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

def run_server(port, use_ssl=False):
    os.chdir(DIST)
    server = http.server.HTTPServer(("0.0.0.0", port), PortalHandler)
    if use_ssl:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(CERT, KEY)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
    proto = "https" if use_ssl else "http"
    print(f"   {proto.upper()} → 0.0.0.0:{port}")
    server.serve_forever()

if __name__ == "__main__":
    host = os.environ.get("TRAEFIK_HOST", "localhost")
    print(f"🚀 FBIB Deploy Hub — Portal Server")
    print(f"   🌐 Public: https://{host}")
    print(f"   📁 Static: {DIST}")
    print(f"   🔌 API proxy → {API_HOST}")

    # Start HTTP on separate thread, HTTPS on main
    t = threading.Thread(target=run_server, args=(80, False), daemon=True)
    t.start()
    run_server(443, use_ssl=True)
