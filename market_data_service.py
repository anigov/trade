import sqlite3
from pathlib import Path

from data.market_data_store import ensure_db, get_ohlcv, insert_rows

DB_PATH = Path(__file__).resolve().parent / 'data' / 'market_data.db'


def fetch_historical_from_open_source():
    """Placeholder that would call a vendor API or open-source provider and normalize rows."""
    return []


def load_latest_market_data_from_broker():
    """Placeholder for broker data integration, e.g. Zerodha Dhan Mirae live feed."""
    return []


def sync_historical_data():
    rows = fetch_historical_from_open_source()
    if rows:
        insert_rows(rows)
    return get_ohlcv()


def sync_realtime_bars():
    rows = load_latest_market_data_from_broker()
    if rows:
        insert_rows(rows)
    return get_ohlcv()


if __name__ == '__main__':
    ensure_db()
    print('Database ready:', DB_PATH)
    print('Historical rows:', len(get_ohlcv()))
