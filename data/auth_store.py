import hashlib
import re
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from data.database import connect_db, execute_sql
from data.market_data_store import ensure_db

PASSWORD_HASHER = PasswordHasher()
USERNAME_PATTERN = re.compile(r'^[a-z0-9._-]{3,48}$')


def _hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create_user(username, password):
    normalized_username = str(username).strip().lower()
    if not USERNAME_PATTERN.fullmatch(normalized_username):
        raise ValueError('Username must be 3–48 characters using letters, numbers, dot, underscore, or hyphen.')
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError('Password must be at least 12 characters long.')

    ensure_db()
    connection = connect_db()
    try:
        execute_sql(
            connection,
            'INSERT INTO app_users (username, password_hash) VALUES (?, ?)',
            (normalized_username, PASSWORD_HASHER.hash(password)),
        )
        connection.commit()
    except Exception as error:
        connection.rollback()
        if getattr(error, 'sqlstate', None) == '23505' or 'UNIQUE constraint failed' in str(error):
            raise ValueError('That username already exists.') from error
        raise
    finally:
        connection.close()


def authenticate_user(username, password):
    if not isinstance(username, str) or not isinstance(password, str):
        return None
    normalized_username = str(username).strip().lower()
    connection = connect_db()
    try:
        user = execute_sql(
            connection,
            'SELECT id, username, password_hash, role FROM app_users WHERE username = ? AND is_active = 1',
            (normalized_username,),
        ).fetchone()
    finally:
        connection.close()

    if not user:
        return None
    try:
        if not PASSWORD_HASHER.verify(user['password_hash'], password):
            return None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return None

    return {'id': user['id'], 'username': user['username'], 'role': user['role']}


def create_session(user_id, ttl_seconds):
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = int(time.time()) + int(ttl_seconds)
    connection = connect_db()
    try:
        execute_sql(connection, 'DELETE FROM auth_sessions WHERE expires_at <= ?', (int(time.time()),))
        execute_sql(
            connection,
            'INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)',
            (token_hash, user_id, expires_at),
        )
        connection.commit()
    finally:
        connection.close()
    return token, expires_at


def get_session_user(token):
    if not token:
        return None
    connection = connect_db()
    try:
        user = execute_sql(
            connection,
            '''
            SELECT app_users.id, app_users.username, app_users.role
            FROM auth_sessions
            JOIN app_users ON app_users.id = auth_sessions.user_id
            WHERE auth_sessions.token_hash = ?
              AND auth_sessions.expires_at > ?
              AND app_users.is_active = 1
            ''',
            (_hash_token(token), int(time.time())),
        ).fetchone()
        return dict(user) if user else None
    finally:
        connection.close()


def delete_session(token):
    if not token:
        return
    connection = connect_db()
    try:
        execute_sql(connection, 'DELETE FROM auth_sessions WHERE token_hash = ?', (_hash_token(token),))
        connection.commit()
    finally:
        connection.close()
