import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from data.market_data_store import ensure_db, get_ohlcv, seed_demo_data

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / 'data' / 'market_data.db'


def serve_json(payload, status=200):
    body = json.dumps(payload).encode('utf-8')
    return body, status


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/ohlcv':
            symbols = parse_qs(parsed.query).get('symbols', [])
            symbol_list = symbols[0].split(',') if symbols else None
            rows = get_ohlcv(symbols=symbol_list)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(json.dumps(rows).encode('utf-8'))
            return

        if path == '/api/health':
            body, status = serve_json({'status': 'ok', 'db': str(DB_PATH)})
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
            return

        file_path = ROOT / path.lstrip('/')
        if path in ('/', '/index.html'):
            file_path = ROOT / 'strategy-builder.html'

        if file_path.exists() and file_path.is_file():
            content = file_path.read_bytes()
            self.send_response(200)
            if file_path.suffix == '.html':
                self.send_header('Content-Type', 'text/html; charset=utf-8')
            elif file_path.suffix == '.js':
                self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            elif file_path.suffix == '.css':
                self.send_header('Content-Type', 'text/css; charset=utf-8')
            elif file_path.suffix == '.json':
                self.send_header('Content-Type', 'application/json; charset=utf-8')
            else:
                self.send_header('Content-Type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_response(404)
        self.end_headers()


if __name__ == '__main__':
    ensure_db()
    seed_demo_data()
    host = '0.0.0.0'
    port = 8001
    server = ThreadingHTTPServer((host, port), Handler)
    print(f'Serving trade app at http://{host}:{port}')
    server.serve_forever()
