import json
import os
import tempfile
import threading
import unittest
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from unittest.mock import patch

from data.auth_store import authenticate_user, create_session, create_user, delete_session, get_session_user
from data.market_data_store import ensure_db, get_fundamentals, upsert_fundamentals


class AuthStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_override = patch.dict(os.environ, {'DATABASE_URL': f'sqlite:///{self.temp_dir.name}/test.db'})
        self.database_override.start()
        ensure_db()

    def tearDown(self):
        self.database_override.stop()
        self.temp_dir.cleanup()

    def test_password_hash_and_revocable_session(self):
        create_user('dev.alpha', 'a sufficiently long password')
        user = authenticate_user('DEV.ALPHA', 'a sufficiently long password')
        self.assertIsNotNone(user)
        self.assertIsNone(authenticate_user('dev.alpha', 'wrong password'))

        token, _ = create_session(user['id'], 300)
        self.assertEqual(get_session_user(token)['username'], 'dev.alpha')
        delete_session(token)
        self.assertIsNone(get_session_user(token))

    def test_fundamental_records_use_shared_database(self):
        upsert_fundamentals({
            'symbol': 'TEST', 'exchange': 'NSE', 'company_name': 'Test Company',
            'roe_pct': 17.5, 'source': 'unit test', 'as_of_date': '2026-10-27',
        })
        self.assertEqual(get_fundamentals()[0]['symbol'], 'TEST')


class AuthHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_override = patch.dict(os.environ, {'DATABASE_URL': f'sqlite:///{self.temp_dir.name}/http.db'})
        self.database_override.start()
        ensure_db()
        create_user('web.dev', 'another sufficiently long password')

        import server
        self.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        self.base_url = f'http://127.0.0.1:{self.httpd.server_port}'
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.server_thread.join(timeout=3)
        self.database_override.stop()
        self.temp_dir.cleanup()

    def test_health_is_public_but_app_api_requires_login(self):
        with self.opener.open(f'{self.base_url}/api/health') as response:
            self.assertEqual(json.load(response)['status'], 'ok')
        with self.assertRaises(HTTPError) as response:
            self.opener.open(f'{self.base_url}/api/fundamentals')
        self.assertEqual(response.exception.code, 401)
        response.exception.close()

    def test_login_fundamental_write_and_logout(self):
        request = Request(
            f'{self.base_url}/api/auth/login',
            data=json.dumps({'username': 'web.dev', 'password': 'another sufficiently long password'}).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with self.opener.open(request) as response:
            self.assertEqual(response.status, 200)

        with self.opener.open(f'{self.base_url}/api/auth/me') as response:
            self.assertEqual(json.load(response)['user']['username'], 'web.dev')

        record = {
            'symbol': 'TEST', 'exchange': 'NSE', 'company_name': 'Test Company',
            'roe_pct': 17.5, 'source': 'integration test', 'as_of_date': '2026-10-27',
        }
        request = Request(
            f'{self.base_url}/api/fundamentals', data=json.dumps(record).encode(),
            headers={'Content-Type': 'application/json'}, method='POST',
        )
        with self.opener.open(request) as response:
            self.assertEqual(response.status, 201)

        request = Request(f'{self.base_url}/api/auth/logout', data=b'{}', headers={'Content-Type': 'application/json'}, method='POST')
        with self.opener.open(request) as response:
            self.assertTrue(json.load(response)['loggedOut'])
        with self.assertRaises(HTTPError) as response:
            self.opener.open(f'{self.base_url}/api/fundamentals')
        self.assertEqual(response.exception.code, 401)
        response.exception.close()


if __name__ == '__main__':
    unittest.main()
