import argparse
from getpass import getpass
import os

from data.auth_store import create_user
from data.market_data_store import ensure_db


def main():
    if os.environ.get('APP_ENV', 'development').lower() == 'production' and not os.environ.get('DATABASE_URL', '').strip():
        raise SystemExit('DATABASE_URL is required in production; refusing to create an account in local SQLite.')
    parser = argparse.ArgumentParser(description='Create a Trade Lab developer account.')
    parser.add_argument('username', help='Username (3–48 letters, numbers, dot, underscore, or hyphen)')
    args = parser.parse_args()

    password = getpass('New password (minimum 12 characters): ')
    confirmation = getpass('Confirm password: ')
    if password != confirmation:
        parser.error('Passwords do not match.')

    ensure_db()
    try:
        create_user(args.username, password)
    except ValueError as error:
        parser.error(str(error))
    print(f'Created developer account: {args.username.strip().lower()}')


if __name__ == '__main__':
    main()
