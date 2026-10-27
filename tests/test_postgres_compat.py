import os
import uuid
import unittest
from unittest.mock import patch

from data.auth_store import authenticate_user, create_session, create_user, delete_session
from data.database import connect_db, database_health, ensure_db, execute_sql
from data.market_data_store import (
    delete_fundamentals,
    get_fundamentals,
    get_ohlcv,
    insert_rows,
    upsert_fundamentals,
)


POSTGRES_TEST_URL = os.environ.get('POSTGRES_TEST_URL')


@unittest.skipUnless(POSTGRES_TEST_URL, 'POSTGRES_TEST_URL is not configured')
class PostgresCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.database_override = patch.dict(os.environ, {'DATABASE_URL': POSTGRES_TEST_URL})
        self.database_override.start()
        ensure_db()
        suffix = uuid.uuid4().hex[:12].upper()
        self.symbol = f'T{suffix}'
        self.username = f'test_{suffix.lower()}'

    def tearDown(self):
        delete_fundamentals(self.symbol)
        connection = connect_db()
        try:
            execute_sql(connection, 'DELETE FROM ohlcv WHERE symbol = ?', (self.symbol,))
            execute_sql(connection, 'DELETE FROM app_users WHERE username = ?', (self.username,))
            connection.commit()
        finally:
            connection.close()
            self.database_override.stop()

    def test_schema_auth_and_market_crud(self):
        self.assertEqual(database_health()['database'], 'postgresql')
        self.assertEqual(insert_rows([{
            'symbol': self.symbol,
            'exchange': 'NSE',
            'date': '2026-10-27',
            'open': 100,
            'high': 105,
            'low': 99,
            'close': 103,
            'volume': 1000,
            'source': 'postgres integration test',
        }]), 1)
        self.assertEqual(insert_rows([{
            'symbol': self.symbol,
            'exchange': 'NSE',
            'date': '2026-10-27',
            'open': 100,
            'high': 105,
            'low': 99,
            'close': 103,
            'volume': 1000,
            'source': 'postgres integration test',
        }]), 0)
        self.assertEqual(get_ohlcv([self.symbol])[0]['close'], 103)

        upsert_fundamentals({
            'symbol': self.symbol,
            'exchange': 'NSE',
            'company_name': 'Temporary PostgreSQL Test',
            'roe_pct': 23.5,
            'source': 'integration test',
            'as_of_date': '2026-10-27',
        })
        self.assertEqual(next(row for row in get_fundamentals() if row['symbol'] == self.symbol)['roe_pct'], 23.5)
        create_user(self.username, 'a sufficiently long test password')
        user = authenticate_user(self.username, 'a sufficiently long test password')
        self.assertEqual(user['username'], self.username)
        token, _ = create_session(user['id'], 300)
        delete_session(token)


if __name__ == '__main__':
    unittest.main()
