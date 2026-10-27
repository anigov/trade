import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from data.auth_store import authenticate_user, create_session, delete_session, get_session_user
from data.database import database_health, is_postgres
from data.market_data_store import (
    delete_fundamentals,
    ensure_db,
    get_fundamentals,
    get_ohlcv,
    seed_demo_data,
    upsert_fundamentals,
)

ROOT = Path(__file__).resolve().parent
COOKIE_NAME = 'trade_session'
APP_ENV = os.environ.get('APP_ENV', 'development').lower()
SESSION_TTL_SECONDS = int(os.environ.get('SESSION_TTL_SECONDS', '28800'))
COOKIE_SECURE = APP_ENV == 'production' or os.environ.get('COOKIE_SECURE', 'false').lower() == 'true'
MAX_REQUEST_BYTES = 16_384


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def send_json(self, payload, status=200, headers=None):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if headers:
            for name, value in headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def session_user(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            morsel = cookie.get(COOKIE_NAME)
            return get_session_user(morsel.value if morsel else None)
        except (ValueError, KeyError):
            return None

    def read_json(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError('Request body is missing or too large.')
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError('Expected a JSON object.')
        return payload

    def require_session(self, path):
        if self.session_user():
            return True
        if path.startswith('/api/'):
            self.send_json({'error': 'Authentication required.'}, 401)
        else:
            self.send_response(302)
            self.send_header('Location', '/login.html')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
        return False

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/health':
            try:
                self.send_json(database_health())
            except Exception:
                self.send_json({'status': 'unavailable'}, 503)
            return

        if path == '/login.html' or path == '/login.css' or path == '/login.js':
            self.serve_file(ROOT / path.lstrip('/'))
            return

        if path.startswith('/api/') or path not in ('/favicon.ico',):
            if not self.require_session(path):
                return

        if path == '/api/auth/me':
            self.send_json({'user': self.session_user()})
            return

        if path == '/api/ohlcv':
            symbols = parse_qs(parsed.query).get('symbols', [])
            symbol_list = symbols[0].split(',') if symbols else None
            rows = get_ohlcv(symbols=symbol_list)
            self.send_json(rows)
            return

        if path == '/api/fundamentals':
            self.send_json(get_fundamentals())
            return

        if path in ('/', '/index.html'):
            path = '/strategy-builder.html'

        file_path = (ROOT / path.lstrip('/')).resolve()
        if not file_path.is_relative_to(ROOT.resolve()):
            self.send_error(404)
            return
        self.serve_file(file_path)

    def serve_file(self, file_path):
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404)
            return
        content = file_path.read_bytes()
        content_type = {
            '.html': 'text/html; charset=utf-8',
            '.js': 'application/javascript; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.json': 'application/json; charset=utf-8',
        }.get(file_path.suffix, 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == '/api/auth/login':
            try:
                payload = self.read_json()
            except (ValueError, json.JSONDecodeError):
                self.send_json({'error': 'Invalid login request.'}, 400)
                return
            username = payload.get('username', '')
            password = payload.get('password', '')
            user = authenticate_user(username, password)
            if not user:
                self.send_json({'error': 'Invalid username or password.'}, 401)
                return
            token, expires_at = create_session(user['id'], SESSION_TTL_SECONDS)
            cookie = f'{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL_SECONDS}'
            if COOKIE_SECURE:
                cookie += '; Secure'
            self.send_json({'user': user, 'expiresAt': expires_at}, headers={'Set-Cookie': cookie})
            return

        if path == '/api/auth/logout':
            user = self.session_user()
            if not user:
                self.send_json({'error': 'Authentication required.'}, 401)
                return
            cookie = f'{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'
            if COOKIE_SECURE:
                cookie += '; Secure'
            delete_session(self._session_token())
            self.send_json({'loggedOut': True}, headers={'Set-Cookie': cookie})
            return

        if path != '/api/fundamentals':
            self.send_error(404)
            return
        if not self.require_session(path):
            return

        try:
            record = self.read_json()
            upsert_fundamentals(record)
            self.send_json({'saved': True}, 201)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.send_json({'error': str(error)}, 400)

    def _session_token(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            morsel = cookie.get(COOKIE_NAME)
            return morsel.value if morsel else None
        except (ValueError, KeyError):
            return None

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/fundamentals':
            self.send_error(404)
            return
        if not self.require_session(parsed.path):
            return

        query = parse_qs(parsed.query)
        symbol = query.get('symbol', [''])[0]
        exchange = query.get('exchange', ['NSE'])[0]
        if not symbol:
            self.send_json({'error': 'Symbol is required.'}, 400)
        else:
            self.send_json({'deleted': delete_fundamentals(symbol, exchange)})


if __name__ == '__main__':
    if APP_ENV == 'production' and not os.environ.get('DATABASE_URL', '').strip():
        raise RuntimeError('DATABASE_URL must be configured for production; refusing to start with local demo SQLite.')
    ensure_db()
    if APP_ENV != 'production' and not is_postgres() and os.environ.get('SEED_DEMO_DATA', 'true').lower() == 'true':
        seed_demo_data()
    host = '0.0.0.0'
    port = int(os.environ.get('PORT', '8001'))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f'Serving trade app at http://{host}:{port}')
    server.serve_forever()
