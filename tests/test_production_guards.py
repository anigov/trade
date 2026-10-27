import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProductionGuardTests(unittest.TestCase):
    def run_without_database_url(self, script, *args):
        environment = os.environ.copy()
        environment.pop('DATABASE_URL', None)
        environment['APP_ENV'] = 'production'
        return subprocess.run(
            [sys.executable, str(ROOT / script), *args],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_server_refuses_production_sqlite_fallback(self):
        result = self.run_without_database_url('server.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DATABASE_URL must be configured for production', result.stderr)

    def test_account_creation_refuses_production_sqlite_fallback(self):
        result = self.run_without_database_url('create_user.py', 'developer')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DATABASE_URL is required in production', result.stderr)
        self.assertNotIn('New password', result.stderr)


if __name__ == '__main__':
    unittest.main()
