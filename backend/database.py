import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Dict, Any
from sqlmodel import create_engine, Session

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./data/family.db')
RUNNING_IN_CONTAINER = Path('/app').exists()
INSECURE_JWT_SECRETS = {'', 'change-me-in-production', 'please-change-this-secret', 'dev-only-family-tree-secret'}

# SECURE_COOKIE & IS_TESTING
SECURE_COOKIE = os.getenv('SECURE_COOKIE', 'false').lower() == 'true'
IS_TESTING = os.getenv('TESTING') == '1' or 'pytest' in sys.modules or os.getenv('PYTEST_CURRENT_TEST') is not None

JWT_SECRET = os.getenv('JWT_SECRET', '')
PASSWORD_MIN_LENGTH = int(os.getenv('PASSWORD_MIN_LENGTH', '10'))
PHOTO_MAX_BYTES = int(os.getenv('PHOTO_MAX_BYTES', str(5 * 1024 * 1024)))
EXCEL_MAX_BYTES = int(os.getenv('EXCEL_MAX_BYTES', str(10 * 1024 * 1024)))
BACKUP_MAX_BYTES = int(os.getenv('BACKUP_MAX_BYTES', str(50 * 1024 * 1024)))
LOGIN_RATE_LIMIT_MAX = int(os.getenv('LOGIN_RATE_LIMIT_MAX', '5'))
LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('LOGIN_RATE_LIMIT_WINDOW_SECONDS', '900'))
LOGIN_RATE_LIMIT_LOCK_SECONDS = int(os.getenv('LOGIN_RATE_LIMIT_LOCK_SECONDS', '900'))
LOGIN_ATTEMPTS: Dict[str, Dict[str, Any]] = {}

def is_strong_password_value(password: str) -> bool:
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        return False
    if any(ch.isspace() for ch in password):
        return False
    has_letter = any(ch.isalpha() for ch in password)
    has_digit = any(ch.isdigit() for ch in password)
    return has_letter and has_digit

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')

if not IS_TESTING:
    if not JWT_SECRET or JWT_SECRET in INSECURE_JWT_SECRETS:
        raise RuntimeError('JWT_SECRET must be set to a strong non-default value in environment variables')
    if not ADMIN_PASSWORD or ADMIN_PASSWORD == 'admin123' or not is_strong_password_value(ADMIN_PASSWORD):
        raise RuntimeError(f'ADMIN_PASSWORD must be set to a strong non-default value with at least {PASSWORD_MIN_LENGTH} chars including letters and digits')
else:
    if not JWT_SECRET:
        JWT_SECRET = 'dev-only-family-tree-secret'
    if not ADMIN_PASSWORD:
        ADMIN_PASSWORD = 'admin123'

JWT_ALG = 'HS256'

DATA_DIR = Path('/app/data') if RUNNING_IN_CONTAINER else Path('./data')
BACKUP_DIR = DATA_DIR / 'backups'
PHOTO_DIR = DATA_DIR / 'member-photos'
DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

AUTO_BACKUP_RETENTION = 30
MANUAL_BACKUP_REASONS = {'manual'}
RESTORE_SAFETY_REASONS = {'before-restore'}
LOCAL_TIMEZONE = ZoneInfo(os.getenv('APP_TIMEZONE', 'Asia/Shanghai'))

connect_args = {'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

def get_db():
    with Session(engine) as session:
        yield session
