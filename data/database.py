import os
import sqlite3
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = DATA_DIR / 'market_data.db'


def get_database_url():
    url = os.environ.get('DATABASE_URL', '').strip()
    if not url:
        return f'sqlite:///{DEFAULT_SQLITE_PATH}'
    if url.startswith('postgres://'):
        return 'postgresql://' + url.removeprefix('postgres://')
    return url


def is_postgres():
    return get_database_url().startswith(('postgresql://', 'postgresql+psycopg://'))


def _sqlite_path(url):
    prefix = 'sqlite:///'
    if not url.startswith(prefix):
        raise ValueError('DATABASE_URL must use PostgreSQL or SQLite.')
    path = Path(url[len(prefix):])
    return path if path.is_absolute() else (Path.cwd() / path)


def connect_db():
    url = get_database_url()
    if is_postgres():
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(url, row_factory=dict_row, connect_timeout=10)

    path = _sqlite_path(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def execute_sql(connection, statement, params=()):
    if is_postgres():
        statement = statement.replace('?', '%s')
    return connection.execute(statement, params)


def ensure_db():
    identifier = 'BIGSERIAL PRIMARY KEY' if is_postgres() else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    foreign_id = 'BIGINT' if is_postgres() else 'INTEGER'
    connection = connect_db()
    try:
        statements = (
            f'''CREATE TABLE IF NOT EXISTS ohlcv (
                id {identifier},
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                date TEXT NOT NULL,
                open DOUBLE PRECISION NOT NULL,
                high DOUBLE PRECISION NOT NULL,
                low DOUBLE PRECISION NOT NULL,
                close DOUBLE PRECISION NOT NULL,
                volume BIGINT NOT NULL,
                source TEXT NOT NULL,
                UNIQUE(symbol, exchange, date)
            )''',
            '''CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )''',
            f'''CREATE TABLE IF NOT EXISTS company_fundamentals (
                id {identifier},
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL DEFAULT 'NSE',
                company_name TEXT NOT NULL,
                sector TEXT NOT NULL DEFAULT '',
                market_cap_cr DOUBLE PRECISION,
                pe_ratio DOUBLE PRECISION,
                roe_pct DOUBLE PRECISION,
                roce_pct DOUBLE PRECISION,
                debt_equity DOUBLE PRECISION,
                revenue_growth_pct DOUBLE PRECISION,
                profit_growth_pct DOUBLE PRECISION,
                promoter_holding_pct DOUBLE PRECISION,
                source TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, exchange)
            )''',
            f'''CREATE TABLE IF NOT EXISTS app_users (
                id {identifier},
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'developer',
                is_active SMALLINT NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )''',
            f'''CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id {foreign_id} NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                expires_at BIGINT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )''',
            'CREATE INDEX IF NOT EXISTS auth_sessions_expiry_idx ON auth_sessions(expires_at)',
        )
        for statement in statements:
            execute_sql(connection, statement)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def database_health():
    connection = connect_db()
    try:
        execute_sql(connection, 'SELECT 1').fetchone()
        return {'status': 'ok', 'database': 'postgresql' if is_postgres() else 'sqlite'}
    finally:
        connection.close()
