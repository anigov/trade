import math
from pathlib import Path
from datetime import date, timedelta

from data.database import (
    DEFAULT_SQLITE_PATH,
    connect_db,
    ensure_db as ensure_database,
    execute_sql,
)

DB_PATH = DEFAULT_SQLITE_PATH


def ensure_db():
    ensure_database()


def insert_rows(rows):
    if not rows:
        return 0

    conn = connect_db()
    inserted = 0
    try:
        for row in rows:
            cursor = execute_sql(
                conn,
                '''
                INSERT INTO ohlcv (symbol, exchange, date, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, exchange, date) DO NOTHING
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
            inserted += cursor.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
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
    conn = connect_db()
    try:
        return int(execute_sql(conn, 'SELECT COUNT(*) AS total FROM ohlcv').fetchone()['total'])
    finally:
        conn.close()


def get_ohlcv(symbols=None, limit=None):
    conn = connect_db()
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
    rows = execute_sql(conn, query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


FUNDAMENTAL_FIELDS = (
    'market_cap_cr',
    'pe_ratio',
    'roe_pct',
    'roce_pct',
    'debt_equity',
    'revenue_growth_pct',
    'profit_growth_pct',
    'promoter_holding_pct',
)


def get_fundamentals():
    conn = connect_db()
    rows = execute_sql(
        conn,
        '''
        SELECT symbol, exchange, company_name, sector, market_cap_cr, pe_ratio,
               roe_pct, roce_pct, debt_equity, revenue_growth_pct,
               profit_growth_pct, promoter_holding_pct, source, as_of_date, updated_at
        FROM company_fundamentals
         ORDER BY LOWER(company_name)
        '''
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def upsert_fundamentals(record):
    symbol = str(record.get('symbol', '')).strip().upper()
    exchange = str(record.get('exchange', 'NSE')).strip().upper()
    company_name = str(record.get('company_name', '')).strip()
    source = str(record.get('source', '')).strip()
    as_of_date = str(record.get('as_of_date', '')).strip()
    if not symbol or not company_name or not source or not as_of_date:
        raise ValueError('Symbol, company name, data source, and as-of date are required.')
    try:
        date.fromisoformat(as_of_date)
    except ValueError as error:
        raise ValueError('As-of date must be a valid ISO date (YYYY-MM-DD).') from error

    values = []
    numeric_values = {}
    for field in FUNDAMENTAL_FIELDS:
        value = record.get(field)
        numeric_value = None if value in (None, '') else float(value)
        if numeric_value is not None and not math.isfinite(numeric_value):
            raise ValueError(f'{field} must be a finite number.')
        values.append(numeric_value)
        numeric_values[field] = numeric_value

    if all(value is None for value in values):
        raise ValueError('Enter at least one fundamental metric.')
    if numeric_values['market_cap_cr'] is not None and numeric_values['market_cap_cr'] < 0:
        raise ValueError('Market capitalization cannot be negative.')
    if numeric_values['debt_equity'] is not None and numeric_values['debt_equity'] < 0:
        raise ValueError('Debt/equity cannot be negative.')
    if numeric_values['promoter_holding_pct'] is not None and not 0 <= numeric_values['promoter_holding_pct'] <= 100:
        raise ValueError('Promoter holding must be between 0 and 100 percent.')

    conn = connect_db()
    execute_sql(
        conn,
        '''
        INSERT INTO company_fundamentals (
            symbol, exchange, company_name, sector, market_cap_cr, pe_ratio,
            roe_pct, roce_pct, debt_equity, revenue_growth_pct,
            profit_growth_pct, promoter_holding_pct, source, as_of_date, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(symbol, exchange) DO UPDATE SET
            company_name = excluded.company_name,
            sector = excluded.sector,
            market_cap_cr = excluded.market_cap_cr,
            pe_ratio = excluded.pe_ratio,
            roe_pct = excluded.roe_pct,
            roce_pct = excluded.roce_pct,
            debt_equity = excluded.debt_equity,
            revenue_growth_pct = excluded.revenue_growth_pct,
            profit_growth_pct = excluded.profit_growth_pct,
            promoter_holding_pct = excluded.promoter_holding_pct,
            source = excluded.source,
            as_of_date = excluded.as_of_date,
            updated_at = CURRENT_TIMESTAMP
        ''',
        (symbol, exchange, company_name, str(record.get('sector', '')).strip(), *values, source, as_of_date),
    )
    conn.commit()
    conn.close()


def delete_fundamentals(symbol, exchange='NSE'):
    conn = connect_db()
    cursor = execute_sql(
        conn,
        'DELETE FROM company_fundamentals WHERE symbol = ? AND exchange = ?',
        (str(symbol).strip().upper(), str(exchange).strip().upper()),
    )
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


if __name__ == '__main__':
    ensure_db()
    inserted = seed_demo_data()
    print(f'Initialized market_data.db with {count_rows()} records; inserted={inserted}')
