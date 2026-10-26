import sqlite3
from pathlib import Path
from datetime import date, timedelta

DB_PATH = Path(__file__).resolve().parent / 'market_data.db'


def ensure_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS ohlcv (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            exchange TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            source TEXT NOT NULL,
            UNIQUE(symbol, exchange, date)
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        '''
    )
    conn.commit()
    conn.close()


def insert_rows(rows):
    if not rows:
        return 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    inserted = 0
    for row in rows:
        try:
            cursor.execute(
                '''
                INSERT INTO ohlcv (symbol, exchange, date, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    row['symbol'],
                    row.get('exchange', 'NSE'),
                    row['date'],
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row['volume']),
                    row.get('source', 'demo'),
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            continue
    conn.commit()
    conn.close()
    return inserted


def seed_demo_data():
    ensure_db()
    symbols = {
        'RELIANCE': 2700,
        'TCS': 3400,
        'INFY': 1450,
    }

    start = date(2025, 1, 1)
    rows = []
    for symbol, base in symbols.items():
        price = base
        for i in range(30):
            current = start + timedelta(days=i)
            drift = (i % 7) * 2.5
            swing = ((i % 5) - 2) * 4.8
            open_price = round(price, 2)
            close_price = round(open_price + drift + swing / 3, 2)
            high = round(max(open_price, close_price) + 8.5 + (i % 4) * 1.6, 2)
            low = round(min(open_price, close_price) - 7.2 - (i % 3) * 1.4, 2)
            volume = 120000 + (i * 7000) + (len(symbol) * 8000)
            rows.append({
                'symbol': symbol,
                'exchange': 'NSE',
                'date': current.isoformat(),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close_price,
                'volume': int(volume),
                'source': 'demo-seed',
            })
            price = close_price

    existing = count_rows()
    if existing == 0:
        inserted = insert_rows(rows)
        return inserted
    return 0


def count_rows():
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute('SELECT COUNT(*) FROM ohlcv').fetchone()[0]
    conn.close()
    return count


def get_ohlcv(symbols=None, limit=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    query = 'SELECT symbol, exchange, date, open, high, low, close, volume, source FROM ohlcv'
    params = []
    if symbols:
        placeholders = ', '.join('?' for _ in symbols)
        query += f' WHERE symbol IN ({placeholders})'
        params.extend(symbols)
    query += ' ORDER BY symbol, date ASC'
    if limit:
        query += ' LIMIT ?'
        params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


if __name__ == '__main__':
    ensure_db()
    inserted = seed_demo_data()
    print(f'Initialized market_data.db with {count_rows()} records; inserted={inserted}')
