import os
import base64
import hashlib
import hmac
import shutil
import json
import sqlite3
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import time
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal
from urllib.parse import quote

import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse, Response
from jose import jwt, JWTError
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Session, create_engine, select

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./data/family.db')
RUNNING_IN_CONTAINER = Path('/app').exists()
INSECURE_JWT_SECRETS = {'', 'change-me-in-production', 'please-change-this-secret'}
JWT_SECRET = os.getenv('JWT_SECRET', '')
if RUNNING_IN_CONTAINER and JWT_SECRET in INSECURE_JWT_SECRETS:
    raise RuntimeError('JWT_SECRET must be set to a strong non-default value in production')
if JWT_SECRET in INSECURE_JWT_SECRETS:
    JWT_SECRET = 'dev-only-family-tree-secret'
JWT_ALG = 'HS256'
PASSWORD_MIN_LENGTH = int(os.getenv('PASSWORD_MIN_LENGTH', '10'))
PHOTO_MAX_BYTES = int(os.getenv('PHOTO_MAX_BYTES', str(5 * 1024 * 1024)))
EXCEL_MAX_BYTES = int(os.getenv('EXCEL_MAX_BYTES', str(10 * 1024 * 1024)))
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
if RUNNING_IN_CONTAINER and (not ADMIN_PASSWORD or ADMIN_PASSWORD == 'admin123' or not is_strong_password_value(ADMIN_PASSWORD)):
    raise RuntimeError(f'ADMIN_PASSWORD must be set to a strong non-default value with at least {PASSWORD_MIN_LENGTH} chars including letters and digits')
if not ADMIN_PASSWORD:
    ADMIN_PASSWORD = 'admin123'
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


def local_now() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)


def local_timestamp_for_filename() -> str:
    return local_now().strftime('%Y%m%d-%H%M%S')


def local_iso_from_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, LOCAL_TIMEZONE).isoformat()


def parse_backup_filename_time(path: Path) -> Optional[datetime]:
    match = re.match(r'^family-(\d{8}-\d{6})-', path.name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), '%Y%m%d-%H%M%S').replace(tzinfo=LOCAL_TIMEZONE)
    except ValueError:
        return None


def backup_created_at(path: Path) -> str:
    parsed = parse_backup_filename_time(path)
    if parsed:
        return parsed.isoformat()
    return local_iso_from_timestamp(path.stat().st_mtime)


def sqlite_path() -> Path:
    if DATABASE_URL.startswith('sqlite:////'):
        return Path('/' + DATABASE_URL.removeprefix('sqlite:////'))
    if DATABASE_URL.startswith('sqlite:///'):
        return Path(DATABASE_URL.removeprefix('sqlite:///'))
    return DATA_DIR / 'family.db'

connect_args = {'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/login')

class Member(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    former_name: Optional[str] = None
    courtesy_name: Optional[str] = None
    art_name: Optional[str] = None
    childhood_name: Optional[str] = None
    gender: Optional[str] = None
    generation: Optional[int] = Field(default=None, index=True)
    generation_name: Optional[str] = None
    rank_no: Optional[int] = None
    rank_title: Optional[str] = None
    branch: Optional[str] = None
    is_core_member: Optional[bool] = True
    birth_date: Optional[str] = None
    birth_calendar: Optional[str] = None
    birth_lunar_date: Optional[str] = None
    birth_is_leap_month: Optional[bool] = False
    birth_date_text: Optional[str] = None
    death_date: Optional[str] = None
    death_calendar: Optional[str] = None
    death_lunar_date: Optional[str] = None
    death_is_leap_month: Optional[bool] = False
    death_date_text: Optional[str] = None
    birth_place: Optional[str] = None
    death_place: Optional[str] = None
    residence: Optional[str] = None
    ancestral_origin: Optional[str] = None
    burial_place: Optional[str] = None
    burial_lat: Optional[float] = None
    burial_lng: Optional[float] = None
    photo_path: Optional[str] = None
    is_living: Optional[bool] = True
    spouse_name: Optional[str] = None
    spouse_ids: Optional[str] = None
    father_name: Optional[str] = None
    father_id: Optional[int] = None
    mother_name: Optional[str] = None
    mother_id: Optional[int] = None
    children_note: Optional[str] = None
    marriage_year: Optional[str] = None
    marriage_note: Optional[str] = None
    education: Optional[str] = None
    occupation: Optional[str] = None
    position_title: Optional[str] = None
    biography: Optional[str] = None
    source: Optional[str] = None
    is_public: Optional[bool] = True
    privacy_level: Optional[str] = Field(default='public', index=True)
    primary_family_id: Optional[int] = Field(default=None, index=True)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class MemberCreate(BaseModel):
    name: str
    former_name: Optional[str] = None
    courtesy_name: Optional[str] = None
    art_name: Optional[str] = None
    childhood_name: Optional[str] = None
    gender: Optional[str] = None
    generation: Optional[int] = None
    generation_name: Optional[str] = None
    rank_no: Optional[int] = None
    rank_title: Optional[str] = None
    branch: Optional[str] = None
    is_core_member: Optional[bool] = True
    birth_date: Optional[str] = None
    birth_calendar: Optional[str] = None
    birth_lunar_date: Optional[str] = None
    birth_is_leap_month: Optional[bool] = False
    birth_date_text: Optional[str] = None
    death_date: Optional[str] = None
    death_calendar: Optional[str] = None
    death_lunar_date: Optional[str] = None
    death_is_leap_month: Optional[bool] = False
    death_date_text: Optional[str] = None
    birth_place: Optional[str] = None
    death_place: Optional[str] = None
    residence: Optional[str] = None
    ancestral_origin: Optional[str] = None
    burial_place: Optional[str] = None
    burial_lat: Optional[float] = None
    burial_lng: Optional[float] = None
    photo_path: Optional[str] = None
    is_living: Optional[bool] = True
    spouse_name: Optional[str] = None
    spouse_ids: Optional[List[int]] = None
    father_name: Optional[str] = None
    father_id: Optional[int] = None
    mother_name: Optional[str] = None
    mother_id: Optional[int] = None
    children_note: Optional[str] = None
    marriage_year: Optional[str] = None
    marriage_note: Optional[str] = None
    education: Optional[str] = None
    occupation: Optional[str] = None
    position_title: Optional[str] = None
    biography: Optional[str] = None
    source: Optional[str] = None
    is_public: Optional[bool] = True
    privacy_level: Optional[str] = 'public'
    primary_family_id: Optional[int] = None

class MemberUpdate(MemberCreate):
    # PUT/PATCH-style update payload: every field is optional and only submitted
    # fields are applied. This prevents partial API clients from accidentally
    # overwriting unspecified member fields with None/default values.
    name: Optional[str] = None

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    role: str = Field(default='viewer', index=True)
    is_active: bool = True
    display_name: Optional[str] = None
    member_id: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_login_at: Optional[str] = None

class FamilyGroup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    surname: Optional[str] = None
    site_title: Optional[str] = None
    cover_kicker: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    root_member_id: Optional[int] = None
    primary_line: str = 'paternal'
    is_primary: bool = Field(default=False, index=True)
    is_active: bool = Field(default=True, index=True)
    sort_order: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class MemberFamilyLink(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    member_id: int = Field(index=True)
    family_id: int = Field(index=True)
    relation_type: str = Field(default='primary', index=True)
    is_primary: bool = Field(default=False, index=True)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class UserFamilyRole(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    family_id: int = Field(index=True)
    role: str = Field(default='viewer', index=True)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: Optional[int] = Field(default=None, index=True)
    actor_username: Optional[str] = Field(default=None, index=True)
    actor_role: Optional[str] = None
    action: str = Field(index=True)
    target_type: Optional[str] = Field(default=None, index=True)
    target_id: Optional[str] = None
    target_label: Optional[str] = None
    detail_json: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), index=True)

class SourceRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    source_type: Optional[str] = Field(default=None, index=True)
    author: Optional[str] = None
    repository: Optional[str] = None
    reference: Optional[str] = None
    url: Optional[str] = None
    note: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Citation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    member_id: int = Field(index=True)
    source_id: int = Field(index=True)
    field_name: Optional[str] = Field(default=None, index=True)
    quote_text: Optional[str] = None
    note: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ReviewRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: Optional[int] = Field(default=None, index=True)
    actor_username: Optional[str] = Field(default=None, index=True)
    actor_role: Optional[str] = None
    member_id: int = Field(index=True)
    target_label: Optional[str] = None
    payload_json: str
    diff_json: Optional[str] = None
    status: str = Field(default='pending', index=True)
    reviewer_user_id: Optional[int] = None
    reviewer_username: Optional[str] = None
    review_note: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), index=True)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'

class CurrentUserOut(BaseModel):
    id: int
    username: str
    displayName: str
    role: str
    capabilities: List[str]
    isActive: bool
    memberId: Optional[int] = None

class ManagedUserOut(BaseModel):
    id: int
    username: str
    displayName: str
    role: str
    roleLabel: str
    capabilities: List[str]
    isActive: bool
    memberId: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    lastLoginAt: Optional[str] = None

class ManagedUserCreate(BaseModel):
    username: str
    password: str
    role: str = 'viewer'
    displayName: Optional[str] = None
    memberId: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    isActive: bool = True

class ManagedUserUpdate(BaseModel):
    role: Optional[str] = None
    displayName: Optional[str] = None
    memberId: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    isActive: Optional[bool] = None

class PasswordResetPayload(BaseModel):
    password: str

class AuditLogOut(BaseModel):
    id: int
    actorUserId: Optional[int] = None
    actorUsername: Optional[str] = None
    actorRole: Optional[str] = None
    action: str
    targetType: Optional[str] = None
    targetId: Optional[str] = None
    targetLabel: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None
    createdAt: str

class SourceIn(BaseModel):
    title: str
    source_type: Optional[str] = None
    author: Optional[str] = None
    repository: Optional[str] = None
    reference: Optional[str] = None
    url: Optional[str] = None
    note: Optional[str] = None

class CitationIn(BaseModel):
    source_id: int
    field_name: Optional[str] = None
    quote_text: Optional[str] = None
    note: Optional[str] = None

class ReviewRejectPayload(BaseModel):
    note: Optional[str] = None

class SiteSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: Optional[str] = None
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class FieldVisibilityTemplateConfig(BaseModel):
    viewer: Literal['public', 'archive', 'sensitive'] = 'public'
    editor: Literal['public', 'archive', 'sensitive'] = 'archive'


class AppSettings(BaseModel):
    siteTitle: str = '陈氏宗族家谱'
    familySurname: str = '陈'
    subtitle: str = '承先祖之德 · 启后世之贤'
    coverKicker: str = 'CHEN CLAN · GENEALOGY'
    treeDescription: str = '可阅读的大型关系结构 · 分层对齐 · 拖拽缩放'
    memberVisibleFields: List[str] = [
        'name', 'gender', 'generation', 'generationName', 'rankTitle',
        'branch', 'birthDate', 'birthPlace', 'residence', 'spouse', 'fatherName', 'motherName'
    ]
    fieldVisibilityTemplates: FieldVisibilityTemplateConfig = FieldVisibilityTemplateConfig()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title='Family Tree System', version='1.0.0', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv('CORS_ORIGIN', 'http://localhost:8088'), 'http://localhost:5173', 'http://localhost:8088'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

MEMBER_SQLITE_EXTRA_COLUMNS = {
    'former_name': 'TEXT',
    'courtesy_name': 'TEXT',
    'art_name': 'TEXT',
    'childhood_name': 'TEXT',
    'branch': 'TEXT',
    'is_core_member': 'INTEGER DEFAULT 1',
    'birth_calendar': 'TEXT',
    'birth_lunar_date': 'TEXT',
    'birth_is_leap_month': 'INTEGER DEFAULT 0',
    'birth_date_text': 'TEXT',
    'death_calendar': 'TEXT',
    'death_lunar_date': 'TEXT',
    'death_is_leap_month': 'INTEGER DEFAULT 0',
    'death_date_text': 'TEXT',
    'ancestral_origin': 'TEXT',
    'burial_place': 'TEXT',
    'burial_lat': 'REAL',
    'burial_lng': 'REAL',
    'photo_path': 'TEXT',
    'is_living': 'INTEGER DEFAULT 1',
    'spouse_ids': 'TEXT',
    'father_id': 'INTEGER',
    'mother_id': 'INTEGER',
    'children_note': 'TEXT',
    'marriage_year': 'TEXT',
    'marriage_note': 'TEXT',
    'education': 'TEXT',
    'occupation': 'TEXT',
    'position_title': 'TEXT',
    'biography': 'TEXT',
    'source': 'TEXT',
    'is_public': 'INTEGER DEFAULT 1',
    'privacy_level': "TEXT DEFAULT 'public'",
    'primary_family_id': 'INTEGER',
}

USER_SQLITE_EXTRA_COLUMNS = {
    'role': "TEXT DEFAULT 'viewer'",
    'is_active': 'INTEGER DEFAULT 1',
    'display_name': 'TEXT',
    'member_id': 'INTEGER',
    'email': 'TEXT',
    'phone': 'TEXT',
    'created_at': 'TEXT',
    'updated_at': 'TEXT',
    'last_login_at': 'TEXT',
}

AUDIT_LOG_SQLITE_EXTRA_COLUMNS = {
    'actor_user_id': 'INTEGER',
    'actor_username': 'TEXT',
    'actor_role': 'TEXT',
    'action': 'TEXT',
    'target_type': 'TEXT',
    'target_id': 'TEXT',
    'target_label': 'TEXT',
    'detail_json': 'TEXT',
    'created_at': 'TEXT',
}

def migrate_sqlite_table_columns(table_name: str, columns: Dict[str, str]):
    if not DATABASE_URL.startswith('sqlite'):
        return
    db_path = sqlite_path()
    if not db_path.exists():
        return
    with sqlite3.connect(db_path) as conn:
        existing = {row[1] for row in conn.execute(f'PRAGMA table_info({table_name})').fetchall()}
        for column, column_type in columns.items():
            if column not in existing:
                conn.execute(f'ALTER TABLE {table_name} ADD COLUMN {column} {column_type}')
        conn.commit()

def migrate_sqlite_member_columns():
    migrate_sqlite_table_columns('member', MEMBER_SQLITE_EXTRA_COLUMNS)

def migrate_sqlite_user_columns():
    migrate_sqlite_table_columns('user', USER_SQLITE_EXTRA_COLUMNS)

def migrate_sqlite_audit_log_columns():
    migrate_sqlite_table_columns('auditlog', AUDIT_LOG_SQLITE_EXTRA_COLUMNS)

ROLE_LABELS = {
    'super_admin': '超级管理员',
    'admin': '管理员',
    'editor': '编辑者',
    'viewer': '只读成员',
}

ROLE_CAPABILITIES = {
    'super_admin': {
        'member.view', 'member.create', 'member.edit_profile', 'member.edit_core_relation', 'member.delete', 'member.import',
        'tree.view', 'tree.locate', 'tree.edit_structure',
        'backup.view', 'backup.create', 'backup.download', 'backup.delete', 'backup.restore',
        'settings.view', 'settings.edit_basic', 'settings.edit_display', 'settings.edit_security',
        'family.view', 'family.create', 'family.edit', 'family.delete',
        'user.view', 'user.create', 'user.edit_role', 'user.disable', 'user.reset_password',
        'audit.view', 'quality.view', 'review.view', 'review.approve', 'source.view', 'source.manage', 'export.gedcom',
    },
    'admin': {
        'member.view', 'member.create', 'member.edit_profile', 'member.edit_core_relation', 'member.delete', 'member.import',
        'tree.view', 'tree.locate', 'tree.edit_structure',
        'backup.view', 'backup.create', 'backup.download',
        'settings.view', 'settings.edit_basic', 'settings.edit_display',
        'family.view', 'family.edit',
        'audit.view', 'quality.view', 'review.view', 'review.approve', 'source.view', 'source.manage', 'export.gedcom',
    },
    'editor': {
        'member.view', 'member.create', 'member.edit_profile', 'review.create', 'source.view', 'source.manage',
        'tree.view', 'tree.locate',
    },
    'viewer': {
        'member.view', 'source.view',
        'tree.view', 'tree.locate',
    },
}

FIELD_VISIBILITY_TEMPLATES = {
    'public': {
        'id', 'name', 'gender', 'generation', 'generationName', 'rankTitle', 'branch',
        'birthDate', 'birthCalendar', 'birthLunarDate', 'birthDateText', 'birthPlace', 'residence', 'spouse', 'fatherName', 'motherName', 'isLiving', 'photoUrl', 'privacyLevel'
    },
    'archive': {
        'id', 'name', 'formerName', 'courtesyName', 'artName', 'childhoodName',
        'gender', 'generation', 'generationName', 'rankNo', 'rankTitle', 'branch', 'isCoreMember',
        'birthDate', 'birthCalendar', 'birthLunarDate', 'birthIsLeapMonth', 'birthDateText',
        'deathDate', 'deathCalendar', 'deathLunarDate', 'deathIsLeapMonth', 'deathDateText',
        'birthPlace', 'deathPlace', 'residence', 'ancestralOrigin',
        'burialPlace', 'burialLat', 'burialLng', 'photoUrl', 'isLiving', 'spouse', 'fatherName', 'motherName',
        'childrenNote', 'marriageYear', 'marriageNote', 'education', 'occupation', 'positionTitle',
        'source', 'isPublic', 'privacyLevel'
    },
    'sensitive': {
        'id', 'name', 'formerName', 'courtesyName', 'artName', 'childhoodName',
        'gender', 'generation', 'generationName', 'rankNo', 'rankTitle', 'branch', 'isCoreMember',
        'birthDate', 'birthCalendar', 'birthLunarDate', 'birthIsLeapMonth', 'birthDateText',
        'deathDate', 'deathCalendar', 'deathLunarDate', 'deathIsLeapMonth', 'deathDateText',
        'birthPlace', 'deathPlace', 'residence', 'ancestralOrigin',
        'burialPlace', 'photoUrl', 'isLiving', 'spouse', 'fatherName', 'motherName',
        'childrenNote', 'marriageYear', 'marriageNote', 'education', 'occupation', 'positionTitle',
        'biography', 'source', 'isPublic', 'privacyLevel'
    },
}


# 关系基础可见字段：用于堂/表亲及其后代在族谱图中“知道有这个人和关系”，但不开放完整档案。
BASIC_RELATION_FIELDS = {
    'id', 'name', 'gender', 'generation', 'generationName', 'rankTitle', 'branch',
    'privacyLevel'
}
VISIBILITY_SCOPE_FULL = 'full'
VISIBILITY_SCOPE_BASIC = 'basic'
VISIBILITY_LABELS = {
    VISIBILITY_SCOPE_FULL: '完整可见',
    VISIBILITY_SCOPE_BASIC: '关系基础可见',
}


def normalize_template_name(name: Optional[str], fallback: str) -> str:
    if not isinstance(name, str):
        return fallback
    lowered = name.strip().lower()
    return lowered if lowered in FIELD_VISIBILITY_TEMPLATES else fallback


PRIVACY_LEVELS = {'public', 'login', 'branch', 'admin'}
PRIVACY_LABELS = {
    'public': '公开',
    'login': '登录可见',
    'branch': '本分支可见',
    'admin': '仅管理员可见',
}

def normalize_privacy_level(value: Optional[str], is_public: Optional[bool] = True) -> str:
    if is_public is False and not value:
        return 'admin'
    level = str(value or 'public').strip().lower()
    return level if level in PRIVACY_LEVELS else 'public'


def can_view_member_privacy(user: User, member: Member, scope_ids: Optional[set[int]]) -> bool:
    if is_unrestricted_user(user):
        return True
    level = normalize_privacy_level(member.privacy_level, member.is_public)
    if level == 'admin':
        return False
    if level == 'branch' and (scope_ids is None or member.id not in scope_ids):
        return False
    return True


IDENTITY_CORE_FIELDS = {
    'name', 'former_name', 'courtesy_name', 'art_name', 'childhood_name', 'gender'
}

STRUCTURE_CORE_FIELDS = {
    'generation', 'generation_name', 'rank_no', 'rank_title', 'branch', 'is_core_member',
    'spouse_name', 'spouse_ids', 'father_name', 'father_id', 'mother_name', 'mother_id',
    'primary_family_id'
}

ARCHIVE_PROFILE_FIELDS = {
    'birth_date', 'birth_calendar', 'birth_lunar_date', 'birth_is_leap_month', 'birth_date_text',
    'death_date', 'death_calendar', 'death_lunar_date', 'death_is_leap_month', 'death_date_text',
    'birth_place', 'death_place', 'residence', 'ancestral_origin',
    'burial_place', 'burial_lat', 'burial_lng', 'photo_path', 'is_living', 'children_note', 'marriage_year', 'marriage_note', 'education', 'occupation',
    'position_title', 'biography', 'source'
}

SYSTEM_CONTROL_FIELDS = {
    'is_public', 'privacy_level'
}

PROFILE_FIELDS = IDENTITY_CORE_FIELDS | ARCHIVE_PROFILE_FIELDS | SYSTEM_CONTROL_FIELDS
CORE_RELATION_FIELDS = STRUCTURE_CORE_FIELDS
ALL_MEMBER_FIELDS = IDENTITY_CORE_FIELDS | STRUCTURE_CORE_FIELDS | ARCHIVE_PROFILE_FIELDS | SYSTEM_CONTROL_FIELDS

AUDIT_FIELD_CATEGORIES = {
    **{field: 'identity' for field in IDENTITY_CORE_FIELDS},
    **{field: 'structure' for field in STRUCTURE_CORE_FIELDS},
    **{field: 'archive' for field in ARCHIVE_PROFILE_FIELDS},
    **{field: 'system' for field in SYSTEM_CONTROL_FIELDS},
}

HIGH_SENSITIVITY_STRUCTURE_FIELDS = {
    'father_id', 'mother_id', 'spouse_ids', 'generation', 'generation_name', 'rank_no', 'rank_title', 'branch', 'is_core_member'
}

HIGH_SENSITIVITY_ARCHIVE_FIELDS = {
    'source'
}

HIGH_SENSITIVITY_FIELDS = HIGH_SENSITIVITY_STRUCTURE_FIELDS | HIGH_SENSITIVITY_ARCHIVE_FIELDS

def run_auto_organization(session: Session):
    unorganized_family = session.exec(select(FamilyGroup).where(FamilyGroup.id == 1)).first()
    m1 = session.get(Member, 1)
    if unorganized_family and (unorganized_family.name == '陈氏宗族' or unorganized_family.surname == '陈') and m1 and m1.name == '王金龙':
        # 1. Rename family 1 to 王氏家族
        unorganized_family.name = '王氏家族'
        unorganized_family.surname = '王'
        unorganized_family.site_title = '王氏家族家谱'
        unorganized_family.cover_kicker = 'WANG CLAN'
        unorganized_family.subtitle = '王氏支系'
        unorganized_family.root_member_id = 1
        unorganized_family.is_primary = True
        session.add(unorganized_family)
        
        # 2. Create the other 8 family groups
        families = [
            (2, "孙氏家族", "孙", "孙氏家族家谱", "SUN CLAN", "孙氏支系", 8),
            (3, "顾氏家族", "顾", "顾氏家族家谱", "GU CLAN", "顾氏支系", 11),
            (4, "曹氏家族", "曹", "曹氏家族家谱", "CAO CLAN", "曹氏支系", 14),
            (5, "周氏家族", "周", "周氏家族家谱", "ZHOU CLAN", "周氏支系", 18),
            (6, "季氏家族", "季", "季氏家族家谱", "JI CLAN", "季氏支系", 19),
            (7, "成氏家族", "成", "成氏家族家谱", "CHENG CLAN", "成氏支系", 23),
            (8, "洪氏家族", "洪", "洪氏家族家谱", "HONG CLAN", "洪氏支系", 30),
            (9, "张氏家族", "张", "张氏家族家谱", "ZHANG CLAN", "张氏支系", 33)
        ]
        for fid, name, surname, title, kicker, subtitle, root_id in families:
            existing = session.get(FamilyGroup, fid)
            if not existing:
                fg = FamilyGroup(
                    id=fid,
                    name=name,
                    surname=surname,
                    site_title=title,
                    cover_kicker=kicker,
                    subtitle=subtitle,
                    root_member_id=root_id,
                    is_primary=False,
                    is_active=True,
                    sort_order=0,
                    primary_line='paternal'
                )
                session.add(fg)
        
        # 3. Update all 41 existing members' primary_family_id
        member_primary_family = {
            1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 7: 1, 13: 1, 15: 1, 17: 1, 28: 1, 29: 1, 36: 1, 37: 1,
            8: 2, 9: 2, 20: 2, 21: 2, 22: 2, 6: 2, 31: 2, 25: 2, 26: 2, 39: 2, 41: 2,
            11: 3, 12: 3, 10: 3, 27: 3, 40: 3,
            14: 4, 16: 4,
            18: 5, 34: 5,
            19: 6, 35: 6,
            23: 7, 24: 7, 38: 7,
            30: 8, 32: 8,
            33: 9
        }
        for mid, fid in member_primary_family.items():
            m = session.get(Member, mid)
            if m:
                m.primary_family_id = fid
                session.add(m)
                
        # 4. Clear and recreate member family links
        existing_links = session.exec(select(MemberFamilyLink)).all()
        for link in existing_links:
            session.delete(link)
            
        # Add primary links
        for mid, fid in member_primary_family.items():
            link = MemberFamilyLink(member_id=mid, family_id=fid, relation_type='primary', is_primary=True)
            session.add(link)
            
        # Add secondary links
        secondary_links = [
            (6, 1), (10, 1), (14, 1), (18, 1), (19, 4), (23, 2), (27, 2), (30, 1), (33, 8), (36, 7), (41, 3)
        ]
        for mid, fid in secondary_links:
            link = MemberFamilyLink(member_id=mid, family_id=fid, relation_type='secondary', is_primary=False)
            session.add(link)
            
        session.commit()

def init_db():
    SQLModel.metadata.create_all(engine)
    migrate_sqlite_member_columns()
    migrate_sqlite_user_columns()
    migrate_sqlite_audit_log_columns()
    with Session(engine) as session:
        ensure_default_family_group(session)
        ensure_member_primary_family(session)
        run_auto_organization(session)
        ensure_default_admin(session)

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 200000)
    return 'pbkdf2_sha256$200000$' + base64.b64encode(salt).decode('utf-8') + '$' + base64.b64encode(digest).decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = password_hash.split('$', 3)
        if scheme != 'pbkdf2_sha256':
            return False
        salt = base64.b64decode(salt_b64.encode('utf-8'))
        expected = base64.b64decode(digest_b64.encode('utf-8'))
        actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

def ensure_default_family_group(session: Session):
    family = session.exec(select(FamilyGroup).where(FamilyGroup.is_primary == True)).first()
    if not family:
        # Load from settings file if exists
        settings = AppSettings()
        family = FamilyGroup(
            name=settings.familySurname + '氏宗族',
            surname=settings.familySurname,
            site_title=settings.siteTitle,
            subtitle=settings.subtitle,
            cover_kicker=settings.coverKicker,
            is_primary=True,
            is_active=True
        )
        session.add(family)
        session.commit()
        session.refresh(family)
    return family

def ensure_member_primary_family(session: Session):
    primary_family = session.exec(select(FamilyGroup).where(FamilyGroup.is_primary == True)).first()
    if not primary_family:
        return
    
    # Update members missing primary_family_id
    members = session.exec(select(Member).where(Member.primary_family_id == None)).all()
    for member in members:
        member.primary_family_id = primary_family.id
        session.add(member)
    if members:
        session.commit()

def ensure_default_admin(session: Session):
    admin = session.exec(select(User).where(User.username == 'admin')).first()
    if admin:
        if admin.role not in ROLE_CAPABILITIES:
            admin.role = 'super_admin'
        if not admin.password_hash:
            admin.password_hash = hash_password(ADMIN_PASSWORD)
        session.add(admin)
        session.commit()
        return admin
    admin = User(
        username='admin',
        display_name='系统管理员',
        role='super_admin',
        is_active=True,
        password_hash=hash_password(ADMIN_PASSWORD),
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin

def create_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=7)
    return jwt.encode({'sub': user.username, 'uid': user.id, 'role': user.role, 'exp': exp}, JWT_SECRET, algorithm=JWT_ALG)

def get_user_capabilities(user: User) -> set[str]:
    return set(ROLE_CAPABILITIES.get(user.role, ROLE_CAPABILITIES['viewer']))

def current_user_payload(user: User) -> Dict[str, Any]:
    return {
        'id': user.id,
        'username': user.username,
        'displayName': user.display_name or user.username,
        'role': user.role,
        'capabilities': sorted(get_user_capabilities(user)),
        'isActive': bool(user.is_active),
        'memberId': user.member_id,
    }

def managed_user_payload(user: User) -> Dict[str, Any]:
    role = user.role if user.role in ROLE_CAPABILITIES else 'viewer'
    return {
        'id': user.id,
        'username': user.username,
        'displayName': user.display_name or user.username,
        'role': role,
        'roleLabel': ROLE_LABELS.get(role, role),
        'capabilities': sorted(ROLE_CAPABILITIES.get(role, ROLE_CAPABILITIES['viewer'])),
        'isActive': bool(user.is_active),
        'memberId': user.member_id,
        'email': user.email,
        'phone': user.phone,
        'createdAt': user.created_at,
        'updatedAt': user.updated_at,
        'lastLoginAt': user.last_login_at,
    }

def validate_role(role: Optional[str]) -> Optional[str]:
    if role is None:
        return None
    if role not in ROLE_CAPABILITIES:
        raise HTTPException(status_code=400, detail='角色不存在')
    return role

def validate_new_password(password: str):
    if not is_strong_password_value(password):
        raise HTTPException(status_code=400, detail=f'密码至少需要 {PASSWORD_MIN_LENGTH} 位，且必须包含字母和数字，不能包含空白字符')


def login_rate_limit_key(request: Request, username: str) -> str:
    forwarded_for = request.headers.get('x-forwarded-for', '')
    ip = forwarded_for.split(',', 1)[0].strip() or (request.client.host if request.client else 'unknown')
    return f'{ip}:{(username or "").strip().lower()}'


def check_login_rate_limit(request: Request, username: str):
    now = time.monotonic()
    key = login_rate_limit_key(request, username)
    row = LOGIN_ATTEMPTS.get(key)
    if not row:
        return
    if now - row.get('first_attempt_at', now) > LOGIN_RATE_LIMIT_WINDOW_SECONDS:
        LOGIN_ATTEMPTS.pop(key, None)
        return
    locked_until = row.get('locked_until', 0)
    if locked_until and now < locked_until:
        retry_after = max(1, int(locked_until - now))
        raise HTTPException(status_code=429, detail=f'登录失败次数过多，请 {retry_after} 秒后再试', headers={'Retry-After': str(retry_after)})


def record_login_failure(request: Request, username: str):
    now = time.monotonic()
    key = login_rate_limit_key(request, username)
    row = LOGIN_ATTEMPTS.get(key)
    if not row or now - row.get('first_attempt_at', now) > LOGIN_RATE_LIMIT_WINDOW_SECONDS:
        row = {'count': 0, 'first_attempt_at': now, 'locked_until': 0}
    row['count'] = int(row.get('count', 0)) + 1
    if row['count'] >= LOGIN_RATE_LIMIT_MAX:
        row['locked_until'] = now + LOGIN_RATE_LIMIT_LOCK_SECONDS
    LOGIN_ATTEMPTS[key] = row


def clear_login_failures(request: Request, username: str):
    LOGIN_ATTEMPTS.pop(login_rate_limit_key(request, username), None)

def resolve_user_member_id(session: Session, member_id: Optional[int]) -> Optional[int]:
    if member_id in (None, ''):
        return None
    member = session.get(Member, int(member_id))
    if not member:
        raise HTTPException(status_code=400, detail='绑定成员不存在')
    return member.id

PHOTO_ALLOWED_TYPES = {
    '.jpg': {'image/jpeg'},
    '.jpeg': {'image/jpeg'},
    '.png': {'image/png'},
    '.webp': {'image/webp'},
}


def detect_image_mime(header: bytes) -> Optional[str]:
    if header.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if len(header) >= 12 and header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'image/webp'
    return None


def validate_photo_upload(file: UploadFile, suffix: str):
    allowed_mimes = PHOTO_ALLOWED_TYPES.get(suffix)
    if not allowed_mimes:
        raise HTTPException(status_code=400, detail='仅支持 JPG/PNG/WebP 照片')
    declared_mime = (file.content_type or '').split(';', 1)[0].strip().lower()
    if declared_mime and declared_mime not in allowed_mimes:
        raise HTTPException(status_code=400, detail='照片 MIME 类型与文件后缀不匹配')
    header = file.file.read(512)
    file.file.seek(0)
    detected_mime = detect_image_mime(header)
    if detected_mime not in allowed_mimes:
        raise HTTPException(status_code=400, detail='照片文件内容不是有效的 JPG/PNG/WebP 图片')


def save_limited_upload(file: UploadFile, target: Path, max_bytes: int, label: str = '文件'):
    total = 0
    try:
        with target.open('wb') as f:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(status_code=413, detail=f'{label}不能超过 {max_bytes // (1024 * 1024)}MB')
                f.write(chunk)
    except Exception:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    if total <= 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f'{label}为空')

def sanitize_audit_detail(detail: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not detail:
        return None

    skip = object()

    def sanitize_value(value: Any, *, nested: bool = False):
        if value is None:
            return None if nested else skip
        if value in ('', [], {}, ()):
            return skip
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            cleaned_list = []
            for item in value:
                cleaned_item = sanitize_value(item, nested=True)
                if cleaned_item is not skip:
                    cleaned_list.append(cleaned_item)
            return cleaned_list or skip
        if isinstance(value, dict):
            cleaned_dict: Dict[str, Any] = {}
            for k, v in value.items():
                cleaned_value = sanitize_value(v, nested=True)
                if cleaned_value is not skip:
                    cleaned_dict[str(k)] = cleaned_value
            return cleaned_dict or skip
        return str(value)

    sanitized: Dict[str, Any] = {}
    for key, value in detail.items():
        cleaned = sanitize_value(value)
        if cleaned is not skip:
            sanitized[key] = cleaned
    return sanitized or None

def write_audit_log(
    session: Session,
    actor: Optional[User],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None,
    target_label: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
):
    sanitized_detail = sanitize_audit_detail(detail)
    row = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_username=actor.username if actor else None,
        actor_role=actor.role if actor else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        target_label=target_label,
        detail_json=json.dumps(sanitized_detail, ensure_ascii=False) if sanitized_detail else None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(row)


def classify_member_change_detail(changed: Dict[str, Any]) -> Dict[str, Any]:
    categories: Dict[str, list[str]] = {}
    high_sensitivity: Dict[str, list[str]] = {}
    for key, diff in (changed or {}).items():
        category = AUDIT_FIELD_CATEGORIES.get(key, 'other')
        categories.setdefault(category, []).append(key)
        if key in HIGH_SENSITIVITY_FIELDS:
            high_key = 'structure' if key in HIGH_SENSITIVITY_STRUCTURE_FIELDS else 'archive'
            high_sensitivity.setdefault(high_key, []).append(key)
    detail: Dict[str, Any] = {
        'fieldCategories': categories,
        'highSensitivity': high_sensitivity,
        'changes': changed,
    }
    if high_sensitivity:
        detail['auditPriority'] = 'high'
    return detail

def audit_log_payload(row: AuditLog) -> Dict[str, Any]:
    detail = None
    if row.detail_json:
        try:
            detail = json.loads(row.detail_json)
        except Exception:
            detail = {'raw': row.detail_json}
    return {
        'id': row.id,
        'actorUserId': row.actor_user_id,
        'actorUsername': row.actor_username,
        'actorRole': row.actor_role,
        'action': row.action,
        'targetType': row.target_type,
        'targetId': row.target_id,
        'targetLabel': row.target_label,
        'detail': detail,
        'createdAt': row.created_at,
    }

def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        username = payload.get('sub')
        if not username:
            raise HTTPException(status_code=401, detail='登录状态无效')
    except JWTError:
        raise HTTPException(status_code=401, detail='登录状态无效')
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail='账号不存在或已停用')
        return user

def is_unrestricted_user(user: User) -> bool:
    return user.role in {'super_admin', 'admin'}

def build_member_visibility(session: Session, user: User) -> Optional[Dict[str, set[int]]]:
    """Return per-user member visibility tiers.

    Non-admin “族人视角”分为两层：
    - full：本人、配偶、父母/祖父母锚点、子女后代及这些完整范围成员的配偶。
    - basic：兄弟姐妹、父母兄弟姐妹、堂/表亲及堂/表亲后代，只开放基础关系信息。
    """
    if is_unrestricted_user(user):
        return None
    if not user.member_id:
        return {VISIBILITY_SCOPE_FULL: set(), VISIBILITY_SCOPE_BASIC: set()}

    members = session.exec(select(Member)).all()
    by_id = {m.id: m for m in members if m.id is not None}
    by_name: Dict[str, List[Member]] = {}
    for m in members:
        nm = normalize_name_value(m.name)
        if nm:
            by_name.setdefault(nm, []).append(m)

    anchor = by_id.get(user.member_id)
    if not anchor:
        return {VISIBILITY_SCOPE_FULL: set(), VISIBILITY_SCOPE_BASIC: set()}

    def first_by_name(name: Optional[str]) -> Optional[Member]:
        return (by_name.get(normalize_name_value(name)) or [None])[0] if normalize_name_value(name) else None

    def relation_parent_ids(member: Member) -> list[int]:
        ids: list[int] = []
        for parent_id, parent_name in [(member.father_id, member.father_name), (member.mother_id, member.mother_name)]:
            pid = parent_id
            if not pid:
                parent = first_by_name(parent_name)
                pid = parent.id if parent and parent.id else None
            if pid and pid in by_id and pid not in ids:
                ids.append(pid)
        return ids

    children_by_parent_id: Dict[int, List[Member]] = {}
    child_seen_by_parent: Dict[int, set[int]] = {}
    spouse_ids_by_member_id: Dict[int, set[int]] = {m.id: set() for m in members if m.id is not None}

    def add_child(parent_id: Optional[int], child: Member):
        if not parent_id or not child.id:
            return
        seen = child_seen_by_parent.setdefault(parent_id, set())
        if child.id in seen:
            return
        seen.add(child.id)
        children_by_parent_id.setdefault(parent_id, []).append(child)

    for m in members:
        add_child(m.father_id, m)
        add_child(m.mother_id, m)
        parsed_spouse_ids = parse_spouse_ids_value(m.spouse_ids)
        if parsed_spouse_ids and m.id is not None:
            for sid in parsed_spouse_ids:
                if sid in by_id:
                    spouse_ids_by_member_id.setdefault(m.id, set()).add(sid)
                    spouse_ids_by_member_id.setdefault(sid, set()).add(m.id)

    # 兼容只有姓名关系、没有 id 关系的旧数据。
    for m in members:
        if not m.father_id:
            parent = first_by_name(m.father_name)
            add_child(parent.id if parent else None, m)
        if not m.mother_id:
            parent = first_by_name(m.mother_name)
            add_child(parent.id if parent else None, m)
        for sp_name in split_relation_names(m.spouse_name):
            spouse = first_by_name(sp_name)
            if spouse and spouse.id and m.id:
                spouse_ids_by_member_id.setdefault(m.id, set()).add(spouse.id)
                spouse_ids_by_member_id.setdefault(spouse.id, set()).add(m.id)

    def add_descendants(root_id: Optional[int], target: set[int], *, include_root: bool = True):
        if not root_id:
            return
        queue = [root_id]
        visited: set[int] = set()
        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)
            if include_root or current_id != root_id:
                target.add(current_id)
            for child in children_by_parent_id.get(current_id, []):
                if child.id and child.id not in visited:
                    queue.append(child.id)

    full_ids: set[int] = set()
    basic_ids: set[int] = set()

    # 完整可见：本人 + 子女后代。
    add_descendants(anchor.id, full_ids, include_root=True)

    def add_ancestor_anchors(member_id: Optional[int], remaining_generations: int = 2):
        if not member_id or remaining_generations <= 0:
            return
        member = by_id.get(member_id)
        if not member:
            return
        for parent_id in relation_parent_ids(member):
            full_ids.add(parent_id)
            add_ancestor_anchors(parent_id, remaining_generations - 1)

    # 完整可见：父母/祖父母作为阅读锚点。
    add_ancestor_anchors(anchor.id, 2)

    # 完整可见：完整范围成员的配偶，但不因配偶继续展开其原生家庭。
    changed = True
    while changed:
        changed = False
        for member_id in list(full_ids):
            for spouse_id in spouse_ids_by_member_id.get(member_id, set()):
                if spouse_id not in full_ids:
                    full_ids.add(spouse_id)
                    changed = True

    # 基础关系可见：兄弟姐妹及其后代。
    for parent_id in relation_parent_ids(anchor):
        for sibling in children_by_parent_id.get(parent_id, []):
            if sibling.id and sibling.id != anchor.id:
                add_descendants(sibling.id, basic_ids, include_root=True)

    # 基础关系可见：父母兄弟姐妹、堂/表亲及堂/表亲后代。
    # 这里从父母各自的父母（也就是本人的祖父母/外祖父母）下找“父母的兄弟姐妹”，
    # 再递归纳入这些分支的后代，满足“表亲/堂亲后代也基础可见”。
    for parent_id in relation_parent_ids(anchor):
        parent = by_id.get(parent_id)
        if not parent:
            continue
        for grandparent_id in relation_parent_ids(parent):
            for parent_sibling in children_by_parent_id.get(grandparent_id, []):
                if not parent_sibling.id or parent_sibling.id == parent_id:
                    continue
                add_descendants(parent_sibling.id, basic_ids, include_root=True)

    # 基础关系不覆盖完整可见。
    basic_ids.difference_update(full_ids)

    return {VISIBILITY_SCOPE_FULL: full_ids, VISIBILITY_SCOPE_BASIC: basic_ids}


def build_member_scope(session: Session, user: User) -> Optional[set[int]]:
    visibility = build_member_visibility(session, user)
    if visibility is None:
        return None
    return set(visibility.get(VISIBILITY_SCOPE_FULL, set())) | set(visibility.get(VISIBILITY_SCOPE_BASIC, set()))


def build_member_full_scope(session: Session, user: User) -> Optional[set[int]]:
    visibility = build_member_visibility(session, user)
    if visibility is None:
        return None
    return set(visibility.get(VISIBILITY_SCOPE_FULL, set()))


def can_view_member_with_visibility(user: User, member: Member, visibility: Optional[Dict[str, set[int]]]) -> bool:
    if is_unrestricted_user(user) or visibility is None:
        return True
    level = normalize_privacy_level(member.privacy_level, member.is_public)
    if level == 'admin':
        return False
    member_id = member.id
    if member_id in visibility.get(VISIBILITY_SCOPE_FULL, set()):
        return True
    if member_id in visibility.get(VISIBILITY_SCOPE_BASIC, set()):
        # 关系基础可见只暴露基础字段；即使是“本分支可见”，也不开放完整档案。
        return True
    return False


def member_visibility_scope(member_id: Optional[int], visibility: Optional[Dict[str, set[int]]]) -> str:
    if visibility is None:
        return VISIBILITY_SCOPE_FULL
    if member_id in visibility.get(VISIBILITY_SCOPE_FULL, set()):
        return VISIBILITY_SCOPE_FULL
    if member_id in visibility.get(VISIBILITY_SCOPE_BASIC, set()):
        return VISIBILITY_SCOPE_BASIC
    return VISIBILITY_SCOPE_BASIC


def visible_fields_for_scope(default_fields: Optional[set[str]], scope: str) -> Optional[set[str]]:
    if scope == VISIBILITY_SCOPE_BASIC:
        return set(BASIC_RELATION_FIELDS)
    return default_fields


def attach_visibility_payload(payload: Dict[str, Any], scope: str) -> Dict[str, Any]:
    payload['visibilityScope'] = scope
    payload['visibilityLabel'] = VISIBILITY_LABELS.get(scope, scope)
    if scope == VISIBILITY_SCOPE_BASIC:
        # 基础关系成员不暴露配偶档案入口和隐私字段细节。
        payload.pop('spouse', None)
        payload.pop('spouseIds', None)
        payload.pop('privacyLabel', None)
    return payload

def require_member_in_scope(session: Session, user: User, member: Optional[Member]) -> set[int]:
    if not member:
        raise HTTPException(404, '成员不存在')
    scope_ids = build_member_scope(session, user)
    if scope_ids is None:
        return set()
    if member.id not in scope_ids:
        raise HTTPException(status_code=403, detail='当前账号无权访问该成员')
    return scope_ids


def require_member_in_full_scope(session: Session, user: User, member: Optional[Member]) -> set[int]:
    if not member:
        raise HTTPException(404, '成员不存在')
    scope_ids = build_member_full_scope(session, user)
    if scope_ids is None:
        return set()
    if member.id not in scope_ids:
        raise HTTPException(status_code=403, detail='当前账号只能查看该成员基础关系，不能编辑完整档案')
    return scope_ids

def require_capability(capability: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if capability not in get_user_capabilities(user):
            raise HTTPException(status_code=403, detail='当前账号无权执行此操作')
        return user
    return dependency

def get_user_family_role(session: Session, user: User, family_id: int) -> Optional[str]:
    """Get user's role for a specific family. Returns None if no specific role assigned."""
    if user.role in ('super_admin', 'admin'):
        return user.role
    
    family_role = session.exec(
        select(UserFamilyRole)
        .where(UserFamilyRole.user_id == user.id)
        .where(UserFamilyRole.family_id == family_id)
    ).first()
    
    return family_role.role if family_role else None

def can_edit_family(session: Session, user: User, family_id: int) -> bool:
    """Check if user can edit a specific family."""
    # Super admin and admin can edit all families
    if user.role in ('super_admin', 'admin'):
        return True
    
    # Check family-specific role
    family_role = get_user_family_role(session, user, family_id)
    if family_role in ('admin', 'editor'):
        return True
    
    return False

def can_view_family(session: Session, user: User, family_id: int) -> bool:
    """Check if user can view a specific family."""
    # Everyone can view by default, unless family-level restrictions are implemented later
    return True

def require_family_edit_permission(family_id: int):
    """Dependency to check family edit permission."""
    def dependency(user: User = Depends(get_current_user), session: Session = Depends(lambda: Session(engine))) -> User:
        if not can_edit_family(session, user, family_id):
            raise HTTPException(status_code=403, detail='当前账号无权编辑该家族')
        return user
    return dependency

def filter_member_payload_for_user(user: User, payload: BaseModel, *, for_create: bool) -> Dict[str, Any]:
    data = payload.model_dump(exclude_unset=not for_create)
    caps = get_user_capabilities(user)
    if 'member.edit_core_relation' in caps:
        allowed = ALL_MEMBER_FIELDS
    elif 'member.edit_profile' in caps:
        # Editors may attach a newly created member to their accessible branch,
        # but must not be able to modify existing core relationships by sending
        # crafted update requests.
        creation_structure_bridge_fields = {'father_id', 'mother_id', 'spouse_ids', 'primary_family_id'} if for_create and 'member.create' in caps else set()
        allowed = PROFILE_FIELDS | creation_structure_bridge_fields
    else:
        allowed = set()
    filtered = {k: v for k, v in data.items() if k in allowed}
    if for_create and 'member.create' in caps and 'member.edit_core_relation' not in caps and 'name' not in filtered:
        filtered['name'] = data.get('name')
    return filtered

def normalize_name_value(value: Optional[str]) -> str:
    return str(value or '').strip()


def split_relation_names(text: Optional[str]) -> list[str]:
    raw = normalize_name_value(text)
    if not raw:
        return []
    return [s.strip() for s in re.split(r'[、,，/\s]+', raw) if s.strip()]


def parse_spouse_ids_value(value: Any) -> list[int]:
    if value in (None, '', [], (), {}):
        return []
    if isinstance(value, list):
        items = value
    else:
        try:
            items = json.loads(value) if isinstance(value, str) else list(value)
        except Exception:
            return []
    result: list[int] = []
    for item in items:
        try:
            iv = int(item)
        except Exception:
            continue
        if iv not in result:
            result.append(iv)
    return result


def encode_spouse_ids_value(ids: list[int]) -> Optional[str]:
    clean_ids: list[int] = []
    for item in ids or []:
        try:
            iv = int(item)
        except Exception:
            continue
        if iv not in clean_ids:
            clean_ids.append(iv)
    return json.dumps(clean_ids, ensure_ascii=False) if clean_ids else None


def sync_member_spouse_links(session: Session, member_id: Optional[int], old_spouse_ids: list[int], new_spouse_ids: list[int]):
    if not member_id:
        return
    old_ids = {sid for sid in parse_spouse_ids_value(old_spouse_ids) if sid != member_id}
    new_ids = {sid for sid in parse_spouse_ids_value(new_spouse_ids) if sid != member_id}

    for spouse_id in new_ids:
        spouse = session.get(Member, spouse_id)
        if not spouse:
            continue
        spouse_ids = parse_spouse_ids_value(spouse.spouse_ids)
        if member_id not in spouse_ids:
            spouse_ids.append(member_id)
            spouse.spouse_ids = encode_spouse_ids_value(spouse_ids)
            session.add(spouse)

    for spouse_id in old_ids - new_ids:
        spouse = session.get(Member, spouse_id)
        if not spouse:
            continue
        spouse_ids = [sid for sid in parse_spouse_ids_value(spouse.spouse_ids) if sid != member_id]
        spouse.spouse_ids = encode_spouse_ids_value(spouse_ids)
        session.add(spouse)


def member_has_ancestor(session: Session, member_id: int, ancestor_id: int, *, max_depth: int = 1000) -> bool:
    """Return whether ancestor_id is already in member_id's parent chain."""
    to_visit = [member_id]
    seen: set[int] = set()
    depth = 0
    while to_visit:
        depth += 1
        if depth > max_depth:
            raise HTTPException(status_code=400, detail='亲子关系层级过深或存在循环，请先修正关系')
        current_id = to_visit.pop()
        if current_id in seen:
            continue
        seen.add(current_id)
        member = session.get(Member, current_id)
        if not member:
            continue
        for parent_id in (member.father_id, member.mother_id):
            if not parent_id:
                continue
            if parent_id == ancestor_id:
                return True
            if parent_id not in seen:
                to_visit.append(parent_id)
    return False


def validate_parent_assignment(session: Session, current_member_id: Optional[int], parent: Optional[Member], relation_label: str):
    if not parent or not current_member_id or not parent.id:
        return
    if parent.id == current_member_id:
        raise HTTPException(status_code=400, detail=f'{relation_label}不能指向自己')
    if member_has_ancestor(session, parent.id, current_member_id):
        raise HTTPException(status_code=400, detail=f'{relation_label}不能指向自己的后代，避免形成亲子关系循环')


def resolve_relation_payload(session: Session, payload: Dict[str, Any], current_member_id: Optional[int] = None) -> Dict[str, Any]:
    data = dict(payload)
    members = session.exec(select(Member)).all()
    by_id = {m.id: m for m in members if m.id is not None}
    by_name: Dict[str, List[Member]] = {}
    for m in members:
        nm = normalize_name_value(m.name)
        if nm:
            by_name.setdefault(nm, []).append(m)

    def pick_member(id_value: Any = None, name_value: Optional[str] = None) -> Optional[Member]:
        if id_value not in (None, ''):
            try:
                mid = int(id_value)
            except Exception:
                raise HTTPException(status_code=400, detail='关系成员 ID 非法')
            member = by_id.get(mid)
            if not member:
                raise HTTPException(status_code=400, detail=f'关系成员不存在: {mid}')
            return member
        name = normalize_name_value(name_value)
        if not name:
            return None
        candidates = by_name.get(name, [])
        if not candidates:
            return None
        return candidates[0]

    has_father_payload = 'father_id' in data or 'father_name' in data
    has_mother_payload = 'mother_id' in data or 'mother_name' in data
    has_spouse_payload = 'spouse_ids' in data or 'spouse_name' in data

    if has_father_payload:
        father = pick_member(data.get('father_id'), data.get('father_name'))
        validate_parent_assignment(session, current_member_id, father, '父亲')
        data['father_id'] = father.id if father else None
        data['father_name'] = father.name if father else (normalize_name_value(data.get('father_name')) or None)

    if has_mother_payload:
        mother = pick_member(data.get('mother_id'), data.get('mother_name'))
        validate_parent_assignment(session, current_member_id, mother, '母亲')
        data['mother_id'] = mother.id if mother else None
        data['mother_name'] = mother.name if mother else (normalize_name_value(data.get('mother_name')) or None)

    if has_spouse_payload:
        spouse_candidates: list[Member] = []
        seen_spouse_ids: set[int] = set()
        spouse_id_inputs = data.get('spouse_ids') or []
        if spouse_id_inputs:
            for sid in spouse_id_inputs:
                spouse = pick_member(sid, None)
                if spouse and spouse.id != current_member_id and spouse.id not in seen_spouse_ids:
                    spouse_candidates.append(spouse)
                    seen_spouse_ids.add(spouse.id)
        else:
            for sp_name in split_relation_names(data.get('spouse_name')):
                spouse = pick_member(None, sp_name)
                if spouse and spouse.id != current_member_id and spouse.id not in seen_spouse_ids:
                    spouse_candidates.append(spouse)
                    seen_spouse_ids.add(spouse.id)

        spouse_ids = [sp.id for sp in spouse_candidates if sp.id is not None]
        spouse_names = [sp.name for sp in spouse_candidates if normalize_name_value(sp.name)]
        if spouse_names:
            data['spouse_name'] = '、'.join(spouse_names)
            data['spouse_ids'] = spouse_ids
        else:
            manual_spouse_names = split_relation_names(data.get('spouse_name'))
            data['spouse_name'] = '、'.join(manual_spouse_names) if manual_spouse_names else None
            data['spouse_ids'] = []

    return data


def clean(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    if s in ('', 'nan', 'NaT'):
        return None
    return s

def clean_int(v):
    if pd.isna(v):
        return None
    try:
        return int(float(v))
    except Exception:
        return None


def to_float(v):
    value = clean(v)
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def cn_count(n: int) -> str:
    nums = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
    if 0 <= n <= 10:
        return nums[n]
    if n < 20:
        return '十' + nums[n - 10]
    if n < 100:
        tens, ones = divmod(n, 10)
        return nums[tens] + '十' + (nums[ones] if ones else '')
    return str(n)


def sort_members_for_relation(members: List[Member]) -> List[Member]:
    def sort_key(member: Member):
        return (
            member.generation if member.generation is not None else 999,
            member.rank_no if member.rank_no is not None else 999,
            0 if member.gender == '男' else 1 if member.gender == '女' else 2,
            member.id or 0,
        )
    return sorted(members, key=sort_key)


def get_children_for_member(member: Member, all_members: Optional[List[Member]] = None) -> List[Member]:
    if not member or not all_members:
        return []
    children: list[Member] = []
    seen: set[int] = set()
    member_id = member.id
    member_name = normalize_name_value(member.name)
    for candidate in all_members:
        if candidate.id == member_id:
            continue
        matched = False
        if member_id is not None and (candidate.father_id == member_id or candidate.mother_id == member_id):
            matched = True
        elif member_name and (normalize_name_value(candidate.father_name) == member_name or normalize_name_value(candidate.mother_name) == member_name):
            matched = True
        if matched and candidate.id not in seen:
            children.append(candidate)
            if candidate.id is not None:
                seen.add(candidate.id)
    return sort_members_for_relation(children)


def generate_children_note(member: Member, all_members: Optional[List[Member]] = None) -> Optional[str]:
    children = get_children_for_member(member, all_members)
    if not children:
        return None
    sons = sum(1 for child in children if child.gender == '男')
    daughters = sum(1 for child in children if child.gender == '女')
    unknown = len(children) - sons - daughters
    parts: list[str] = []
    if sons:
        parts.append(f'{cn_count(sons)}子')
    if daughters:
        parts.append(f'{cn_count(daughters)}女')
    if unknown:
        parts.append(f'{cn_count(unknown)}名子女')
    names = '、'.join([child.name for child in children if normalize_name_value(child.name)])
    return f"育有{''.join(parts)}：{names}" if names else f"育有{''.join(parts)}"

def member_to_dict(m: Member, visible_fields: Optional[set[str]] = None, include_relations: bool = True, by_id: Optional[Dict[int, Member]] = None, all_members: Optional[List[Member]] = None) -> Dict[str, Any]:
    relation_by_id = by_id or {}
    spouse_ids = parse_spouse_ids_value(m.spouse_ids)
    spouse_names = [relation_by_id[sid].name for sid in spouse_ids if sid in relation_by_id and normalize_name_value(relation_by_id[sid].name)]
    spouse_display = '、'.join(spouse_names) if spouse_names else m.spouse_name
    father_name = relation_by_id[m.father_id].name if m.father_id in relation_by_id and normalize_name_value(relation_by_id[m.father_id].name) else m.father_name
    mother_name = relation_by_id[m.mother_id].name if m.mother_id in relation_by_id and normalize_name_value(relation_by_id[m.mother_id].name) else m.mother_name
    data = {
        'id': m.id,
        'name': m.name,
        'formerName': m.former_name,
        'courtesyName': m.courtesy_name,
        'artName': m.art_name,
        'childhoodName': m.childhood_name,
        'gender': m.gender,
        'generation': m.generation,
        'generationName': m.generation_name,
        'rankNo': m.rank_no,
        'rankTitle': m.rank_title,
        'branch': m.branch,
        'isCoreMember': m.is_core_member,
        'birthDate': m.birth_date,
        'birthCalendar': m.birth_calendar,
        'birthLunarDate': m.birth_lunar_date,
        'birthIsLeapMonth': m.birth_is_leap_month,
        'birthDateText': m.birth_date_text,
        'deathDate': m.death_date,
        'deathCalendar': m.death_calendar,
        'deathLunarDate': m.death_lunar_date,
        'deathIsLeapMonth': m.death_is_leap_month,
        'deathDateText': m.death_date_text,
        'birthPlace': m.birth_place,
        'deathPlace': m.death_place,
        'residence': m.residence,
        'ancestralOrigin': m.ancestral_origin,
        'burialPlace': m.burial_place,
        'burialLat': m.burial_lat,
        'burialLng': m.burial_lng,
        'photoUrl': m.photo_path,
        'isLiving': m.is_living,
        'spouse': spouse_display,
        'spouseIds': spouse_ids,
        'fatherName': father_name,
        'fatherId': m.father_id,
        'motherName': mother_name,
        'motherId': m.mother_id,
        'childrenNote': m.children_note or generate_children_note(m, all_members),
        'marriageYear': m.marriage_year,
        'marriageNote': m.marriage_note,
        'education': m.education,
        'occupation': m.occupation,
        'positionTitle': m.position_title,
        'biography': m.biography,
        'source': m.source,
        'isPublic': m.is_public,
        'privacyLevel': normalize_privacy_level(m.privacy_level, m.is_public),
        'privacyLabel': PRIVACY_LABELS.get(normalize_privacy_level(m.privacy_level, m.is_public), '公开'),
        'primaryFamilyId': m.primary_family_id,
    }
    if visible_fields is not None:
        visible = set(visible_fields) | {'id', 'name'}
        data = {k: v for k, v in data.items() if k in visible or k in {'fatherId', 'motherId', 'spouseIds'}}
    if include_relations:
        data['spouses'] = []
        data['children'] = []
    return data


def resolve_visible_member_fields(session: Session, user: User) -> Optional[set[str]]:
    if is_unrestricted_user(user):
        return None

    settings = get_settings_dict(session)
    templates = settings.get('fieldVisibilityTemplates') or {}
    viewer_tpl = normalize_template_name((templates or {}).get('viewer'), 'public')
    editor_tpl = normalize_template_name((templates or {}).get('editor'), 'archive')

    if user.role == 'viewer':
        template_name = viewer_tpl
    elif user.role == 'editor':
        template_name = editor_tpl
    else:
        template_name = 'public'

    template_fields = set(FIELD_VISIBILITY_TEMPLATES.get(template_name, FIELD_VISIBILITY_TEMPLATES['public']))

    configured = settings.get('memberVisibleFields') or DEFAULT_SETTINGS.get('memberVisibleFields', [])
    configured_set = {f for f in configured if isinstance(f, str)}

    return template_fields & (configured_set | {'id', 'name'})


def classify_backup_file(path: Path) -> Dict[str, Any]:
    stem = path.stem
    parts = stem.split('-', 3)
    reason = parts[3] if len(parts) >= 4 else 'unknown'
    if reason in MANUAL_BACKUP_REASONS:
        backup_type = 'manual'
        type_label = '手动备份'
        source = '用户手动创建'
        deletable_by_retention = False
    elif reason in RESTORE_SAFETY_REASONS:
        backup_type = 'safety'
        type_label = '恢复前保护备份'
        source = '恢复前自动创建'
        deletable_by_retention = False
    else:
        backup_type = 'auto'
        type_label = '自动备份'
        source_map = {
            'before-create': '新增成员前',
            'before-import': 'Excel 导入前',
            'before-import-default': '导入内置表格前',
            'before-settings-update': '系统设置更新前',
        }
        if reason.startswith('before-update-'):
            source = f"更新成员 #{reason.removeprefix('before-update-')} 前"
        elif reason.startswith('before-delete-'):
            source = f"删除成员 #{reason.removeprefix('before-delete-')} 前"
        else:
            source = source_map.get(reason, reason)
        deletable_by_retention = True
    return {
        'reason': reason,
        'backupType': backup_type,
        'typeLabel': type_label,
        'source': source,
        'isManual': backup_type == 'manual',
        'isAuto': backup_type == 'auto',
        'isSafety': backup_type == 'safety',
        'retentionProtected': not deletable_by_retention,
        'canAutoPrune': deletable_by_retention,
    }


def backup_sort_key(path: Path) -> tuple[float, str]:
    try:
        return (path.stat().st_mtime, path.name)
    except FileNotFoundError:
        return (0, path.name)


def prune_auto_backups() -> List[str]:
    auto_backups = [
        p for p in BACKUP_DIR.glob('family-*.db')
        if classify_backup_file(p).get('canAutoPrune')
    ]
    auto_backups = sorted(auto_backups, key=backup_sort_key, reverse=True)
    pruned: List[str] = []
    for old in auto_backups[AUTO_BACKUP_RETENTION:]:
        try:
            old.unlink()
            pruned.append(old.name)
        except FileNotFoundError:
            pass
    return pruned


def copy_sqlite_database(source: Path, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        destination.touch()
        return
    src = sqlite3.connect(f'file:{source}?mode=ro', uri=True)
    try:
        dst = sqlite3.connect(destination)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def backup_db(reason='manual') -> Dict[str, Any]:
    db = sqlite_path()
    ts = local_timestamp_for_filename()
    safe_reason = re.sub(r'[^A-Za-z0-9_.-]+', '-', str(reason or 'manual')).strip('-') or 'manual'
    backup = BACKUP_DIR / f'family-{ts}-{safe_reason}.db'
    copy_sqlite_database(db, backup)
    pruned = prune_auto_backups()
    meta = classify_backup_file(backup)
    return {'path': str(backup), 'file': backup.name, 'createdAt': backup_created_at(backup), 'createdAtCompact': ts, 'timezone': str(LOCAL_TIMEZONE), 'pruned': pruned, **meta}


def validate_sqlite_backup_file(path: Path):
    try:
        conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=400, detail=f'备份文件无效或已损坏: {exc}') from exc
    try:
        integrity = conn.execute('PRAGMA integrity_check').fetchone()
        if not integrity or integrity[0] != 'ok':
            raise HTTPException(status_code=400, detail='备份文件无效或已损坏，完整性校验失败')
        existing_tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        required_tables = {table.name for table in SQLModel.metadata.sorted_tables}
        missing_tables = sorted(required_tables - existing_tables)
        if missing_tables:
            raise HTTPException(status_code=400, detail=f'备份表结构缺少必要表: {", ".join(missing_tables[:5])}')
    except sqlite3.Error as exc:
        raise HTTPException(status_code=400, detail=f'备份文件无效或已损坏: {exc}') from exc
    finally:
        conn.close()

def clear_member_dependent_records_for_replace_import(session: Session):
    for row in session.exec(select(Citation)).all():
        session.delete(row)
    for row in session.exec(select(ReviewRequest)).all():
        session.delete(row)
    for user in session.exec(select(User)).all():
        if user.member_id is not None:
            user.member_id = None
            user.updated_at = datetime.now(timezone.utc).isoformat()
            session.add(user)
    for m in session.exec(select(Member)).all():
        session.delete(m)


def ensure_member_can_be_deleted(session: Session, member_id: int):
    child = session.exec(select(Member).where((Member.father_id == member_id) | (Member.mother_id == member_id))).first()
    if child:
        raise HTTPException(status_code=409, detail=f'该成员仍被子女「{child.name}」引用，请先调整亲子关系')
    spouse = session.exec(select(Member)).all()
    for candidate in spouse:
        if member_id in parse_spouse_ids_value(candidate.spouse_ids):
            raise HTTPException(status_code=409, detail=f'该成员仍被配偶「{candidate.name}」引用，请先调整配偶关系')
    citation = session.exec(select(Citation).where(Citation.member_id == member_id)).first()
    if citation:
        raise HTTPException(status_code=409, detail='该成员仍有关联资料引用，请先删除或迁移引用')
    review = session.exec(select(ReviewRequest).where(ReviewRequest.member_id == member_id)).first()
    if review:
        raise HTTPException(status_code=409, detail='该成员仍有关联审核请求，请先处理审核请求')
    bound_user = session.exec(select(User).where(User.member_id == member_id)).first()
    if bound_user:
        raise HTTPException(status_code=409, detail=f'该成员仍绑定用户「{bound_user.username}」，请先解除绑定')


def pick_best_parent(candidates: list[Member], child_generation: Optional[int]) -> Optional[Member]:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    if child_generation is None:
        return candidates[0]
    valid_cands = [c for c in candidates if c.generation is not None and c.generation < child_generation]
    if valid_cands:
        # Sort by distance to (child_generation - 1)
        valid_cands.sort(key=lambda c: abs(c.generation - (child_generation - 1)))
        return valid_cands[0]
    return candidates[0]


def pick_best_spouse(candidates: list[Member], member_generation: Optional[int], exclude_id: Optional[int] = None) -> Optional[Member]:
    valid_cands = [c for c in candidates if c.id != exclude_id] if exclude_id else candidates
    if not valid_cands:
        return None
    if len(valid_cands) == 1:
        return valid_cands[0]
    if member_generation is None:
        return valid_cands[0]
    cands_with_gen = [c for c in valid_cands if c.generation is not None]
    if cands_with_gen:
        cands_with_gen.sort(key=lambda c: abs(c.generation - member_generation))
        return cands_with_gen[0]
    return valid_cands[0]


def import_excel(path: str, replace=True) -> int:
    df = pd.read_excel(path, sheet_name=0)
    required = ['姓名','性别','世代','字辈','排行序号','排行称谓','出生日期','去世日期','出生地','去世地','现居住地','配偶','父亲','母亲']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f'缺少字段: {missing}')
    with Session(engine) as session:
        try:
            if replace:
                clear_member_dependent_records_for_replace_import(session)
            
            # 确保默认家族存在
            default_family = ensure_default_family_group(session)
            
            # 如果有"所属家族"列，预先收集所有家族名称并创建/查找
            family_name_to_id = {}
            if '所属家族' in df.columns:
                unique_family_names = set(clean(r['所属家族']) for _, r in df.iterrows() if clean(r['所属家族']))
                for family_name in unique_family_names:
                    if not family_name:
                        continue
                    existing = session.exec(select(FamilyGroup).where(FamilyGroup.name == family_name)).first()
                    if existing:
                        family_name_to_id[family_name] = existing.id
                    else:
                        # 创建新家族
                        new_family = FamilyGroup(name=family_name, description='从导入表格自动创建')
                        session.add(new_family)
                        session.flush()
                        if new_family.id:
                            family_name_to_id[family_name] = new_family.id
            
            count = 0
            member_family_mapping = []  # 保存 (member, family_id) 用于后续建立关联
            
            for _, r in df.iterrows():
                name = clean(r['姓名'])
                if not name:
                    continue
                
                # 确定所属家族
                family_name = clean(r['所属家族']) if '所属家族' in df.columns else None
                primary_family_id = family_name_to_id.get(family_name) if family_name else default_family.id
                
                m = Member(
                    name=name, gender=clean(r['性别']), generation=clean_int(r['世代']),
                    generation_name=clean(r['字辈']), rank_no=clean_int(r['排行序号']), rank_title=clean(r['排行称谓']),
                    birth_date=clean(r['出生日期']), death_date=clean(r['去世日期']), birth_place=clean(r['出生地']),
                    death_place=clean(r['去世地']), residence=clean(r['现居住地']), spouse_name=clean(r['配偶']),
                    burial_place=clean(r['安葬地/墓址']) if '安葬地/墓址' in df.columns else None,
                    burial_lat=to_float(clean(r['安葬纬度'])) if '安葬纬度' in df.columns else None,
                    burial_lng=to_float(clean(r['安葬经度'])) if '安葬经度' in df.columns else None,
                    photo_path=clean(r['照片地址']) if '照片地址' in df.columns else None,
                    father_name=clean(r['父亲']), mother_name=clean(r['母亲']),
                    primary_family_id=primary_family_id
                )
                session.add(m)
                member_family_mapping.append((m, primary_family_id))
                count += 1
            session.flush()

            members = session.exec(select(Member)).all()
            by_name: Dict[str, List[Member]] = {}
            for m in members:
                nm = normalize_name_value(m.name)
                if nm:
                    by_name.setdefault(nm, []).append(m)

            for m in members:
                family_id = m.primary_family_id
                
                # 同家族过滤以及世代差启发式匹配父亲
                father = None
                if normalize_name_value(m.father_name):
                    cands = [x for x in by_name.get(normalize_name_value(m.father_name), []) if x.primary_family_id == family_id]
                    father = pick_best_parent(cands, m.generation)
                
                # 同家族过滤以及世代差启发式匹配母亲
                mother = None
                if normalize_name_value(m.mother_name):
                    cands = [x for x in by_name.get(normalize_name_value(m.mother_name), []) if x.primary_family_id == family_id]
                    mother = pick_best_parent(cands, m.generation)
                
                # 同家族过滤以及世代差启发式匹配配偶
                spouse_members = []
                for sp_name in split_relation_names(m.spouse_name):
                    cands = [x for x in by_name.get(sp_name, []) if x.primary_family_id == family_id]
                    best_sp = pick_best_spouse(cands, m.generation, exclude_id=m.id)
                    if best_sp:
                        spouse_members.append(best_sp)
                        
                uniq_spouse_ids = []
                for sp in spouse_members:
                    if sp.id and sp.id != m.id and sp.id not in uniq_spouse_ids:
                        uniq_spouse_ids.append(sp.id)
                validate_parent_assignment(session, m.id, father, '父亲')
                validate_parent_assignment(session, m.id, mother, '母亲')
                m.father_id = father.id if father else None
                m.mother_id = mother.id if mother else None
                m.spouse_ids = encode_spouse_ids_value(uniq_spouse_ids)
                session.add(m)
            session.flush()
            
            # 建立成员-家族关联
            for member, family_id in member_family_mapping:
                if member.id and family_id:
                    # 检查是否已存在关联
                    existing_link = session.exec(
                        select(MemberFamilyLink).where(
                            MemberFamilyLink.member_id == member.id,
                            MemberFamilyLink.family_id == family_id
                        )
                    ).first()
                    if not existing_link:
                        link = MemberFamilyLink(member_id=member.id, family_id=family_id)
                        session.add(link)
            
            for m in members:
                sync_member_spouse_links(session, m.id, [], parse_spouse_ids_value(m.spouse_ids))
            session.commit()
            return count
        except Exception:
            session.rollback()
            raise


def ensure_import_template() -> Path:
    path = DATA_DIR / 'members-import-template.xlsx'
    columns = ['姓名','性别','世代','字辈','排行序号','排行称谓','出生日期','去世日期','出生地','去世地','现居住地','安葬地/墓址','安葬纬度','安葬经度','照片地址','配偶','父亲','母亲','所属家族']
    sample_rows = [
        {
            '姓名': '张一世', '性别': '男', '世代': 1, '字辈': '德', '排行序号': 1, '排行称谓': '长子',
            '出生日期': '1900-01-01', '去世日期': '', '出生地': '祖籍地', '去世地': '', '现居住地': '',
            '安葬地/墓址': '', '安葬纬度': '', '安葬经度': '', '照片地址': '', '配偶': '李氏', '父亲': '', '母亲': '', '所属家族': ''
        },
        {
            '姓名': '李氏', '性别': '女', '世代': 1, '字辈': '', '排行序号': '', '排行称谓': '',
            '出生日期': '', '去世日期': '', '出生地': '', '去世地': '', '现居住地': '',
            '安葬地/墓址': '', '安葬纬度': '', '安葬经度': '', '照片地址': '', '配偶': '张一世', '父亲': '', '母亲': '', '所属家族': ''
        },
        {
            '姓名': '张二世', '性别': '男', '世代': 2, '字辈': '承', '排行序号': 1, '排行称谓': '长子',
            '出生日期': '1930-01-01', '去世日期': '', '出生地': '祖籍地', '去世地': '', '现居住地': '',
            '安葬地/墓址': '', '安葬纬度': '', '安葬经度': '', '照片地址': '', '配偶': '', '父亲': '张一世', '母亲': '李氏', '所属家族': ''
        },
    ]
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        pd.DataFrame(sample_rows, columns=columns).to_excel(writer, index=False, sheet_name='成员导入')
        pd.DataFrame([
            {'字段': '姓名', '说明': '必填；同名成员会影响父母/配偶匹配，建议保持唯一或后续手工校对'},
            {'字段': '性别', '说明': '建议填写：男 / 女'},
            {'字段': '世代', '说明': '数字，例如 1、2、3'},
            {'字段': '配偶', '说明': '填写配偶姓名；多配偶用中文顿号"、"分隔'},
            {'字段': '父亲/母亲', '说明': '填写表格中已有成员姓名，系统导入后自动建立关系'},
            {'字段': '安葬纬度/安葬经度', '说明': '可选；在编辑页通过地图选点后自动生成，也可手工填写'},
            {'字段': '所属家族', '说明': '可选；填写家族名称（如"张氏宗族"）；为空时使用默认家族'},
        ]).to_excel(writer, index=False, sheet_name='填写说明')
    return path


def build_tree(session: Session, allowed_ids: Optional[set[int]] = None, visible_fields: Optional[set[str]] = None, visible_fields_by_id: Optional[Dict[int, Optional[set[str]]]] = None, visibility_scope_by_id: Optional[Dict[int, str]] = None):
    members = session.exec(select(Member).order_by(Member.generation, Member.rank_no, Member.id)).all()
    if allowed_ids is not None:
        members = [m for m in members if m.id in allowed_ids]

    by_id = {m.id: m for m in members if m.id is not None}
    by_name: Dict[str, List[Member]] = {}
    for m in members:
        nm = normalize_name_value(m.name)
        if nm:
            by_name.setdefault(nm, []).append(m)

    def first_by_name(name: Optional[str]):
        return (by_name.get(normalize_name_value(name)) or [None])[0] if normalize_name_value(name) else None

    def fields_for_member(member_id: Optional[int]) -> Optional[set[str]]:
        if member_id is not None and visible_fields_by_id is not None and member_id in visible_fields_by_id:
            return visible_fields_by_id[member_id]
        return visible_fields

    def scope_for_member(member_id: Optional[int]) -> str:
        if member_id is not None and visibility_scope_by_id is not None:
            return visibility_scope_by_id.get(member_id, VISIBILITY_SCOPE_FULL)
        return VISIBILITY_SCOPE_FULL

    def dict_for_member(member: Member, include_relations: bool = True) -> Dict[str, Any]:
        payload = member_to_dict(member, visible_fields=fields_for_member(member.id), include_relations=include_relations, by_id=by_id, all_members=members)
        return attach_visibility_payload(payload, scope_for_member(member.id))

    nodes = {m.id: dict_for_member(m) for m in members if m.id is not None}
    child_ids = set()

    def spouse_missing_placeholder(name: str):
        return {'id': None, 'name': name, 'gender': None, 'children': [], 'spouses': [], 'visibilityScope': VISIBILITY_SCOPE_BASIC, 'visibilityLabel': VISIBILITY_LABELS[VISIBILITY_SCOPE_BASIC]}

    def can_show_spouse_placeholder(member: Member) -> bool:
        member_fields = fields_for_member(member.id)
        return member_fields is None or 'spouse' in member_fields

    def get_spouse_members(member: Member) -> list[Member]:
        spouse_ids = parse_spouse_ids_value(member.spouse_ids)
        result: list[Member] = []
        seen: set[int] = set()
        for sid in spouse_ids:
            spouse = by_id.get(sid)
            if spouse and spouse.id != member.id and spouse.id not in seen:
                result.append(spouse)
                seen.add(spouse.id)
        if result:
            return result
        for sp_name in split_relation_names(member.spouse_name):
            spouse = first_by_name(sp_name)
            if spouse and spouse.id != member.id and spouse.id not in seen:
                result.append(spouse)
                seen.add(spouse.id)
        return result

    def resolve_parent(member: Member) -> Optional[Member]:
        if member.father_id and member.father_id in by_id:
            return by_id[member.father_id]
        if member.mother_id and member.mother_id in by_id:
            return by_id[member.mother_id]
        return first_by_name(member.father_name) or first_by_name(member.mother_name)

    def parse_rank_title(title: Optional[str]) -> int:
        if not title:
            return 999
        t = str(title).strip()
        if not t:
            return 999
        normalized = (
            t.replace('排行', '')
             .replace('兄', '')
             .replace('弟', '')
             .replace('姐', '')
             .replace('妹', '')
             .replace('儿子', '子')
             .replace('女儿', '女')
        )
        digit_match = re.search(r'(\d+)', normalized)
        if digit_match:
            try:
                return int(digit_match.group(1))
            except ValueError:
                pass
        cn_num_map = {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
        if normalized.startswith('长') or normalized.startswith('大'):
            return 1
        if normalized.startswith('次'):
            return 2
        for key, value in cn_num_map.items():
            if key in normalized:
                return value
        return 999

    def node_sort_key(node: Dict[str, Any]):
        rank_no = node.get('rankNo')
        return (
            node.get('generation') if node.get('generation') is not None else 999,
            rank_no if rank_no is not None else parse_rank_title(node.get('rankTitle')),
            0 if node.get('gender') == '男' else 1 if node.get('gender') == '女' else 2,
            node.get('name') or '',
            node.get('id') or 0,
        )

    def sort_tree_node(node: Dict[str, Any]):
        node['children'] = sorted(node.get('children') or [], key=node_sort_key)
        node['spouses'] = sorted(node.get('spouses') or [], key=node_sort_key)
        for child in node['children']:
            sort_tree_node(child)
        return node

    for m in members:
        if m.id is None:
            continue
        n = nodes[m.id]
        spouse_members = get_spouse_members(m)
        if spouse_members and can_show_spouse_placeholder(m):
            n['spouses'] = [dict_for_member(sp, include_relations=False) for sp in spouse_members]
        elif can_show_spouse_placeholder(m):
            for sp_name in split_relation_names(m.spouse_name):
                n['spouses'].append(spouse_missing_placeholder(sp_name))

    for m in members:
        if m.id is None:
            continue
        parent = resolve_parent(m)
        if parent and parent.id in nodes:
            nodes[parent.id]['children'].append(nodes[m.id])
            child_ids.add(m.id)

    spouse_ids = set()
    for m in members:
        if m.id is None:
            continue
        for sp in get_spouse_members(m):
            if sp.id is None or sp.id == m.id:
                continue
            if m.gender == '男' and sp.gender == '女':
                spouse_ids.add(sp.id)
            elif m.gender == '女' and sp.gender == '男':
                spouse_ids.add(m.id)

    def should_merge_spouse_children_into_member(member: Member, spouse: Member) -> bool:
        """Return whether spouse's children should be folded into member's displayed lineage node.

        The tree is paternal-line oriented: for a heterosexual couple, shared children should be
        rendered under the male/father node only. Merging in both directions makes a wife with
        her own natal parents (e.g. 孙永芳) duplicate the husband's branch under her birth family,
        so the frontend `seen` de-duplication consumes descendants in the wrong branch and makes
        the real paternal branch appear unresponsive.
        """
        if member.gender == '男' and spouse.gender == '女':
            return True
        if member.gender == '女' and spouse.gender == '男':
            return False
        return bool(member.is_core_member) and not bool(spouse.is_core_member)

    for m in members:
        if m.id is None:
            continue
        for sp in get_spouse_members(m):
            if sp.id and sp.id in nodes and sp.id != m.id and should_merge_spouse_children_into_member(m, sp):
                sp_children = nodes[sp.id].get('children', [])
                primary_children = nodes[m.id].setdefault('children', [])
                existing_ids = {c['id'] for c in primary_children}
                for ch in sp_children:
                    if ch['id'] not in existing_ids:
                        primary_children.append(ch)
                        existing_ids.add(ch['id'])

    for node in nodes.values():
        sort_tree_node(node)

    roots = sorted([nodes[m.id] for m in members if m.id is not None and m.id not in child_ids and m.id not in spouse_ids], key=node_sort_key)
    min_gen = min([m.generation for m in members if m.generation is not None], default=None)
    preferred = [r for r in roots if r.get('generation') == min_gen]
    return preferred or roots

DEFAULT_SETTINGS = AppSettings().model_dump()

def decode_setting_value(key: str, value: Optional[str]):
    if value is None:
        return None
    try:
        return json.loads(value)
    except Exception:
        if key == 'memberVisibleFields':
            return [x.strip() for x in value.split(',') if x.strip()]
        return value

def get_settings_dict(session: Session) -> Dict[str, Any]:
    rows = session.exec(select(SiteSetting)).all()
    current = {}
    for row in rows:
        decoded = decode_setting_value(row.key, row.value)
        if decoded is not None:
            current[row.key] = decoded
    return {**DEFAULT_SETTINGS, **current}

def save_settings_dict(session: Session, payload: AppSettings) -> Dict[str, Any]:
    data = payload.model_dump()
    allowed_fields = set(DEFAULT_SETTINGS['memberVisibleFields']) | {
        'formerName', 'courtesyName', 'artName', 'childhoodName', 'rankNo', 'branch',
        'isCoreMember', 'birthCalendar', 'birthLunarDate', 'birthIsLeapMonth', 'birthDateText',
        'deathDate', 'deathCalendar', 'deathLunarDate', 'deathIsLeapMonth', 'deathDateText',
        'deathPlace', 'ancestralOrigin', 'burialPlace', 'isLiving',
        'childrenNote', 'marriageYear', 'marriageNote', 'education', 'occupation', 'positionTitle', 'biography',
        'source', 'isPublic', 'privacyLevel'
    }
    if not data.get('memberVisibleFields'):
        data['memberVisibleFields'] = DEFAULT_SETTINGS['memberVisibleFields']
    data['memberVisibleFields'] = [f for f in data['memberVisibleFields'] if f in allowed_fields]
    if 'name' not in data['memberVisibleFields']:
        data['memberVisibleFields'].insert(0, 'name')

    templates = data.get('fieldVisibilityTemplates') or {}
    data['fieldVisibilityTemplates'] = {
        'viewer': normalize_template_name((templates or {}).get('viewer'), 'public'),
        'editor': normalize_template_name((templates or {}).get('editor'), 'archive'),
    }

    now = datetime.now(timezone.utc).isoformat()
    for key, value in data.items():
        row = session.get(SiteSetting, key)
        if isinstance(value, str):
            clean_value = value.strip() or DEFAULT_SETTINGS.get(key, '')
        else:
            clean_value = value or DEFAULT_SETTINGS.get(key)
        stored_value = json.dumps(clean_value, ensure_ascii=False)
        if row:
            row.value = stored_value
            row.updated_at = now
        else:
            row = SiteSetting(key=key, value=stored_value, updated_at=now)
        session.add(row)
    session.commit()
    return get_settings_dict(session)

def source_payload(row: SourceRecord) -> Dict[str, Any]:
    return {
        'id': row.id,
        'title': row.title,
        'sourceType': row.source_type,
        'author': row.author,
        'repository': row.repository,
        'reference': row.reference,
        'url': row.url,
        'note': row.note,
        'createdAt': row.created_at,
        'updatedAt': row.updated_at,
    }


def citation_payload(row: Citation, source: Optional[SourceRecord] = None) -> Dict[str, Any]:
    return {
        'id': row.id,
        'memberId': row.member_id,
        'sourceId': row.source_id,
        'sourceTitle': source.title if source else None,
        'fieldName': row.field_name,
        'quoteText': row.quote_text,
        'note': row.note,
        'createdAt': row.created_at,
    }


def review_request_payload(row: ReviewRequest) -> Dict[str, Any]:
    def loads(v, fallback):
        try:
            return json.loads(v) if v else fallback
        except Exception:
            return fallback
    return {
        'id': row.id,
        'actorUserId': row.actor_user_id,
        'actorUsername': row.actor_username,
        'actorRole': row.actor_role,
        'memberId': row.member_id,
        'targetLabel': row.target_label,
        'payload': loads(row.payload_json, {}),
        'diff': loads(row.diff_json, {}),
        'status': row.status,
        'reviewerUserId': row.reviewer_user_id,
        'reviewerUsername': row.reviewer_username,
        'reviewNote': row.review_note,
        'createdAt': row.created_at,
        'updatedAt': row.updated_at,
    }


def create_member_review_request_if_changed(session: Session, user: User, member: Member, raw_payload: Dict[str, Any]) -> Optional[ReviewRequest]:
    if not raw_payload:
        return None
    data = resolve_relation_payload(session, raw_payload, current_member_id=member.id)
    if 'spouse_ids' in data:
        data['spouse_ids'] = encode_spouse_ids_value(data.get('spouse_ids') or [])
    allowed_review_fields = CORE_RELATION_FIELDS
    data = {k: v for k, v in data.items() if k in allowed_review_fields}
    before = {key: getattr(member, key, None) for key in data.keys()}
    changed = {
        key: {'before': before.get(key), 'after': data.get(key)}
        for key in data.keys()
        if before.get(key) != data.get(key)
    }
    if not changed:
        return None
    row = ReviewRequest(
        actor_user_id=user.id,
        actor_username=user.username,
        actor_role=user.role,
        member_id=member.id,
        target_label=member.name,
        payload_json=json.dumps(data, ensure_ascii=False),
        diff_json=json.dumps(changed, ensure_ascii=False),
        status='pending',
    )
    session.add(row)
    session.flush()
    write_audit_log(session, user, 'review.create', target_type='member', target_id=member.id, target_label=member.name, detail={'reviewRequestId': row.id, 'changes': changed})
    return row


def build_data_quality_report(session: Session) -> Dict[str, Any]:
    members = session.exec(select(Member)).all()
    by_id = {m.id: m for m in members if m.id is not None}
    issues: list[Dict[str, Any]] = []

    def add(severity: str, category: str, member: Optional[Member], message: str, detail: Optional[Dict[str, Any]] = None):
        issues.append({
            'severity': severity,
            'category': category,
            'memberId': member.id if member else None,
            'memberName': member.name if member else None,
            'message': message,
            'detail': detail or {},
        })

    name_map: Dict[str, List[Member]] = {}
    for m in members:
        nm = normalize_name_value(m.name)
        if nm:
            name_map.setdefault(nm, []).append(m)

    for name, rows in name_map.items():
        if len(rows) > 1:
            add('warning', 'duplicate_name', rows[0], f'存在同名成员「{name}」{len(rows)} 条', {'ids': [r.id for r in rows]})

    min_generation = min([m.generation for m in members if m.generation is not None], default=None)
    cited_member_ids = {c.member_id for c in session.exec(select(Citation)).all()}

    spouse_map = {m.id: set(parse_spouse_ids_value(m.spouse_ids)) for m in members if m.id is not None}
    for m in members:
        if m.id is None:
            continue
        for field, pid in [('father_id', m.father_id), ('mother_id', m.mother_id)]:
            if pid and pid not in by_id:
                add('error', 'invalid_relation', m, f'{field} 指向不存在成员 #{pid}', {'field': field, 'targetId': pid})
        for sid in spouse_map.get(m.id, set()):
            if sid == m.id:
                add('error', 'invalid_relation', m, '配偶不能指向自己', {'spouseId': sid})
            elif sid not in by_id:
                add('error', 'invalid_relation', m, f'配偶指向不存在成员 #{sid}', {'spouseId': sid})
            elif m.id not in spouse_map.get(sid, set()):
                add('warning', 'asymmetric_spouse', m, f'与「{by_id[sid].name}」的配偶关系不是双向', {'spouseId': sid})
        for parent_id in [m.father_id, m.mother_id]:
            parent = by_id.get(parent_id)
            if parent and m.generation is not None and parent.generation is not None and m.generation <= parent.generation:
                add('error', 'generation_anomaly', m, f'成员世代不大于父母「{parent.name}」', {'memberGeneration': m.generation, 'parentGeneration': parent.generation, 'parentId': parent.id})
        if m.is_living and (normalize_name_value(m.death_date) or normalize_name_value(m.death_lunar_date) or normalize_name_value(m.death_date_text)):
            add('warning', 'life_status_conflict', m, '标记健在但存在去世日期/记载')
        if m.is_living is False and not (normalize_name_value(m.death_date) or normalize_name_value(m.death_lunar_date) or normalize_name_value(m.death_date_text)):
            add('info', 'missing_death_info', m, '已故成员缺少去世日期或原始记载')
        if min_generation is not None and m.generation and m.generation > min_generation and not (m.father_id or m.mother_id or normalize_name_value(m.father_name) or normalize_name_value(m.mother_name)):
            add('warning', 'missing_parent', m, '非始祖世代成员缺少父母关系')
        if not normalize_name_value(m.source) and m.id not in cited_member_ids:
            add('info', 'missing_source', m, '缺少资料来源或引用记录')
        if normalize_privacy_level(m.privacy_level, m.is_public) == 'public' and m.is_living:
            add('info', 'privacy_review', m, '健在成员当前为公开级别，建议确认隐私策略')

    summary: Dict[str, Any] = {'total': len(issues), 'bySeverity': {}, 'byCategory': {}}
    for issue in issues:
        summary['bySeverity'][issue['severity']] = summary['bySeverity'].get(issue['severity'], 0) + 1
        summary['byCategory'][issue['category']] = summary['byCategory'].get(issue['category'], 0) + 1
    severity_order = {'error': 0, 'warning': 1, 'info': 2}
    issues.sort(key=lambda x: (severity_order.get(x['severity'], 9), x.get('category') or '', x.get('memberId') or 0))
    return {'summary': summary, 'issues': issues[:500]}


def gedcom_escape(value: Any) -> str:
    return str(value or '').replace('\n', ' ').replace('\r', ' ').strip()


def build_gedcom(session: Session) -> str:
    members = session.exec(select(Member).order_by(Member.id)).all()
    by_id = {m.id: m for m in members if m.id is not None}
    family_keys: Dict[tuple[Optional[int], Optional[int]], Dict[str, Any]] = {}

    def get_family_key(father_id: Optional[int], mother_id: Optional[int]):
        return (father_id, mother_id)

    for m in members:
        if m.father_id or m.mother_id:
            fam = family_keys.setdefault(get_family_key(m.father_id, m.mother_id), {'husb': m.father_id, 'wife': m.mother_id, 'children': []})
            if m.id not in fam['children']:
                fam['children'].append(m.id)
    for m in members:
        for sid in parse_spouse_ids_value(m.spouse_ids):
            if sid not in by_id or not m.id or sid < m.id:
                continue
            sp = by_id[sid]
            husb = m.id if m.gender == '男' else sp.id if sp.gender == '男' else m.id
            wife = sp.id if husb == m.id else m.id
            family_keys.setdefault(get_family_key(husb, wife), {'husb': husb, 'wife': wife, 'children': []})

    fam_ids = {key: idx + 1 for idx, key in enumerate(family_keys.keys())}
    famc_by_child: Dict[int, int] = {}
    fams_by_person: Dict[int, list[int]] = {}
    for key, fam in family_keys.items():
        fid = fam_ids[key]
        for pid in [fam.get('husb'), fam.get('wife')]:
            if pid:
                fams_by_person.setdefault(pid, []).append(fid)
        for cid in fam.get('children') or []:
            famc_by_child[cid] = fid

    lines = [
        '0 HEAD',
        '1 GEDC',
        '2 VERS 7.0',
        '1 SOUR FAMILY-TREE-SYSTEM',
        '1 CHAR UTF-8',
        f"1 DATE {datetime.now(timezone.utc).strftime('%d %b %Y').upper()}",
    ]
    for m in members:
        if m.id is None:
            continue
        lines.append(f'0 @I{m.id}@ INDI')
        lines.append(f'1 NAME {gedcom_escape(m.name)}')
        if m.gender in {'男', '女'}:
            lines.append(f"1 SEX {'M' if m.gender == '男' else 'F'}")
        if m.birth_date or m.birth_place or m.birth_date_text:
            lines.append('1 BIRT')
            if m.birth_date:
                lines.append(f'2 DATE {gedcom_escape(m.birth_date)}')
            if m.birth_place:
                lines.append(f'2 PLAC {gedcom_escape(m.birth_place)}')
            if m.birth_date_text:
                lines.append(f'2 NOTE {gedcom_escape(m.birth_date_text)}')
        if m.is_living is False or m.death_date or m.death_place or m.death_date_text:
            lines.append('1 DEAT')
            if m.death_date:
                lines.append(f'2 DATE {gedcom_escape(m.death_date)}')
            if m.death_place:
                lines.append(f'2 PLAC {gedcom_escape(m.death_place)}')
            if m.death_date_text:
                lines.append(f'2 NOTE {gedcom_escape(m.death_date_text)}')
        for fid in fams_by_person.get(m.id, []):
            lines.append(f'1 FAMS @F{fid}@')
        if m.id in famc_by_child:
            lines.append(f'1 FAMC @F{famc_by_child[m.id]}@')
        notes = []
        if m.generation is not None:
            notes.append(f'世代：{m.generation}')
        if m.generation_name:
            notes.append(f'字辈：{m.generation_name}')
        if m.rank_title:
            notes.append(f'排行：{m.rank_title}')
        if m.branch:
            notes.append(f'支系：{m.branch}')
        if m.biography:
            notes.append(m.biography)
        if m.source:
            notes.append(f'资料来源：{m.source}')
        for note in notes:
            lines.append(f'1 NOTE {gedcom_escape(note)}')
    for key, fam in family_keys.items():
        fid = fam_ids[key]
        lines.append(f'0 @F{fid}@ FAM')
        if fam.get('husb'):
            lines.append(f"1 HUSB @I{fam['husb']}@")
        if fam.get('wife'):
            lines.append(f"1 WIFE @I{fam['wife']}@")
        for cid in fam.get('children') or []:
            lines.append(f'1 CHIL @I{cid}@')
    lines.append('0 TRLR')
    return '\n'.join(lines) + '\n'


@app.get('/admin/data-quality')
def data_quality(_: User = Depends(require_capability('quality.view'))):
    with Session(engine) as session:
        return build_data_quality_report(session)


@app.get('/admin/review-requests')
def list_review_requests(_: User = Depends(require_capability('review.view'))):
    with Session(engine) as session:
        rows = session.exec(select(ReviewRequest).order_by(ReviewRequest.id.desc()).limit(200)).all()
        return [review_request_payload(row) for row in rows]


@app.post('/admin/review-requests/{request_id}/approve')
def approve_review_request(request_id: int, reviewer: User = Depends(require_capability('review.approve'))):
    with Session(engine) as session:
        row = session.get(ReviewRequest, request_id)
        if not row:
            raise HTTPException(404, '审核请求不存在')
        if row.status != 'pending':
            raise HTTPException(400, '审核请求已处理')
        member = session.get(Member, row.member_id)
        if not member:
            raise HTTPException(404, '成员不存在')
        data = json.loads(row.payload_json or '{}')
        
        # 验证新提交的关系是否合法或形成循环
        if 'father_id' in data:
            father_id = data['father_id']
            if father_id:
                father = session.get(Member, father_id)
                if not father:
                    raise HTTPException(400, f'所指父亲成员 #{father_id} 不存在')
                validate_parent_assignment(session, member.id, father, '父亲')
        if 'mother_id' in data:
            mother_id = data['mother_id']
            if mother_id:
                mother = session.get(Member, mother_id)
                if not mother:
                    raise HTTPException(400, f'所指母亲成员 #{mother_id} 不存在')
                validate_parent_assignment(session, member.id, mother, '母亲')
        if 'spouse_ids' in data:
            spouse_ids = parse_spouse_ids_value(data['spouse_ids'])
            for sid in spouse_ids:
                if sid == member.id:
                    raise HTTPException(400, '配偶不能指向自己')
                spouse = session.get(Member, sid)
                if not spouse:
                    raise HTTPException(400, f'所指配偶成员 #{sid} 不存在')

        old_spouse_ids = parse_spouse_ids_value(member.spouse_ids)
        before = {key: getattr(member, key, None) for key in data.keys()}
        for k, v in data.items():
            setattr(member, k, v)
        member.updated_at = datetime.now(timezone.utc).isoformat()
        if 'spouse_ids' in data:
            sync_member_spouse_links(session, member.id, old_spouse_ids, parse_spouse_ids_value(member.spouse_ids))
        if 'primary_family_id' in data:
            new_fam_id = data['primary_family_id']
            old_fam_id = before.get('primary_family_id')
            if old_fam_id != new_fam_id:
                if old_fam_id:
                    old_links = session.exec(select(MemberFamilyLink).where(
                        MemberFamilyLink.member_id == member.id,
                        MemberFamilyLink.family_id == old_fam_id
                    )).all()
                    for l in old_links:
                        session.delete(l)
                if new_fam_id:
                    existing = session.exec(select(MemberFamilyLink).where(
                        MemberFamilyLink.member_id == member.id,
                        MemberFamilyLink.family_id == new_fam_id
                    )).first()
                    if not existing:
                        link = MemberFamilyLink(member_id=member.id, family_id=new_fam_id)
                        session.add(link)
        after = {key: getattr(member, key, None) for key in data.keys()}
        changed = {key: {'before': before.get(key), 'after': after.get(key)} for key in data.keys() if before.get(key) != after.get(key)}
        row.status = 'approved'
        row.reviewer_user_id = reviewer.id
        row.reviewer_username = reviewer.username
        row.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(member)
        session.add(row)
        write_audit_log(session, reviewer, 'review.approve', target_type='member', target_id=member.id, target_label=member.name, detail={'reviewRequestId': row.id, **classify_member_change_detail(changed)})
        session.commit()
        session.refresh(row)
        return review_request_payload(row)


@app.post('/admin/review-requests/{request_id}/reject')
def reject_review_request(request_id: int, payload: ReviewRejectPayload, reviewer: User = Depends(require_capability('review.approve'))):
    with Session(engine) as session:
        row = session.get(ReviewRequest, request_id)
        if not row:
            raise HTTPException(404, '审核请求不存在')
        if row.status != 'pending':
            raise HTTPException(400, '审核请求已处理')
        row.status = 'rejected'
        row.reviewer_user_id = reviewer.id
        row.reviewer_username = reviewer.username
        row.review_note = (payload.note or '').strip() or None
        row.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(row)
        write_audit_log(session, reviewer, 'review.reject', target_type='member', target_id=row.member_id, target_label=row.target_label, detail={'reviewRequestId': row.id, 'note': row.review_note})
        session.commit()
        session.refresh(row)
        return review_request_payload(row)


@app.get('/sources')
def list_sources(_: User = Depends(require_capability('source.view'))):
    with Session(engine) as session:
        rows = session.exec(select(SourceRecord).order_by(SourceRecord.id.desc())).all()
        return [source_payload(row) for row in rows]


@app.post('/sources')
def create_source(payload: SourceIn, user: User = Depends(require_capability('source.manage'))):
    title = (payload.title or '').strip()
    if not title:
        raise HTTPException(400, '来源标题不能为空')
    now = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        row = SourceRecord(
            title=title,
            source_type=(payload.source_type or '').strip() or None,
            author=(payload.author or '').strip() or None,
            repository=(payload.repository or '').strip() or None,
            reference=(payload.reference or '').strip() or None,
            url=(payload.url or '').strip() or None,
            note=(payload.note or '').strip() or None,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        write_audit_log(session, user, 'source.create', target_type='source', target_id=row.id, target_label=row.title)
        session.commit()
        return source_payload(row)


@app.put('/sources/{source_id}')
def update_source(source_id: int, payload: SourceIn, user: User = Depends(require_capability('source.manage'))):
    with Session(engine) as session:
        row = session.get(SourceRecord, source_id)
        if not row:
            raise HTTPException(404, '来源不存在')
        row.title = (payload.title or '').strip() or row.title
        row.source_type = (payload.source_type or '').strip() or None
        row.author = (payload.author or '').strip() or None
        row.repository = (payload.repository or '').strip() or None
        row.reference = (payload.reference or '').strip() or None
        row.url = (payload.url or '').strip() or None
        row.note = (payload.note or '').strip() or None
        row.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(row)
        write_audit_log(session, user, 'source.update', target_type='source', target_id=row.id, target_label=row.title)
        session.commit()
        session.refresh(row)
        return source_payload(row)


@app.delete('/sources/{source_id}')
def delete_source(source_id: int, user: User = Depends(require_capability('source.manage'))):
    with Session(engine) as session:
        row = session.get(SourceRecord, source_id)
        if not row:
            raise HTTPException(404, '来源不存在')
        linked = session.exec(select(Citation).where(Citation.source_id == source_id)).all()
        if linked:
            raise HTTPException(400, '该来源已有引用，不能直接删除')
        title = row.title
        session.delete(row)
        write_audit_log(session, user, 'source.delete', target_type='source', target_id=source_id, target_label=title)
        session.commit()
        return {'ok': True}


@app.get('/members/{member_id}/citations')
def list_member_citations(member_id: int, user: User = Depends(require_capability('source.view'))):
    with Session(engine) as session:
        member = session.get(Member, member_id)
        if not member:
            raise HTTPException(404, '成员不存在')
        visibility = build_member_visibility(session, user)
        if not can_view_member_with_visibility(user, member, visibility):
            raise HTTPException(status_code=403, detail='当前账号无权访问该成员')
        if member_visibility_scope(member.id, visibility) == VISIBILITY_SCOPE_BASIC:
            return []
        rows = session.exec(select(Citation).where(Citation.member_id == member_id).order_by(Citation.id.desc())).all()
        sources = {s.id: s for s in session.exec(select(SourceRecord)).all() if s.id is not None}
        return [citation_payload(row, sources.get(row.source_id)) for row in rows]


@app.post('/members/{member_id}/citations')
def create_member_citation(member_id: int, payload: CitationIn, user: User = Depends(require_capability('source.manage'))):
    with Session(engine) as session:
        member = session.get(Member, member_id)
        require_member_in_full_scope(session, user, member)
        source = session.get(SourceRecord, payload.source_id)
        if not source:
            raise HTTPException(400, '来源不存在')
        row = Citation(
            member_id=member_id,
            source_id=payload.source_id,
            field_name=(payload.field_name or '').strip() or None,
            quote_text=(payload.quote_text or '').strip() or None,
            note=(payload.note or '').strip() or None,
        )
        session.add(row)
        write_audit_log(session, user, 'source.cite', target_type='member', target_id=member_id, target_label=member.name, detail={'sourceId': source.id, 'fieldName': row.field_name})
        session.commit()
        session.refresh(row)
        return citation_payload(row, source)


@app.get('/export/gedcom')
def export_gedcom(_: User = Depends(require_capability('export.gedcom'))):
    with Session(engine) as session:
        content = build_gedcom(session)
    filename = f"family-tree-{local_timestamp_for_filename()}.ged"
    return Response(
        content=content,
        media_type='text/plain; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@app.get('/health')
def health():
    return {'ok': True, 'time': datetime.now(timezone.utc).isoformat()}

@app.post('/auth/login', response_model=Token)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    check_login_rate_limit(request, form.username)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == form.username)).first()
        if not user or not user.is_active or not verify_password(form.password, user.password_hash):
            record_login_failure(request, form.username)
            raise HTTPException(status_code=401, detail='用户名或密码错误')
        clear_login_failures(request, form.username)
        user.last_login_at = datetime.now(timezone.utc).isoformat()
        write_audit_log(session, user, 'auth.login', target_type='user', target_id=user.id, target_label=user.username)
        session.add(user)
        session.commit()
        return Token(access_token=create_token(user))

@app.get('/me', response_model=CurrentUserOut)
def me(user: User = Depends(get_current_user)):
    return current_user_payload(user)

PUBLIC_SETTING_KEYS = {'siteTitle', 'familySurname', 'subtitle', 'coverKicker'}


@app.get('/public-settings')
def get_public_settings():
    with Session(engine) as session:
        settings = get_settings_dict(session)
        return {key: settings.get(key, DEFAULT_SETTINGS.get(key)) for key in PUBLIC_SETTING_KEYS}


@app.get('/settings')
def get_settings(_: User = Depends(require_capability('settings.view'))):
    with Session(engine) as session:
        return get_settings_dict(session)

@app.get('/admin/roles')
def list_roles(_: User = Depends(require_capability('user.view'))):
    return [
        {'role': role, 'label': ROLE_LABELS.get(role, role), 'capabilities': sorted(caps)}
        for role, caps in ROLE_CAPABILITIES.items()
    ]

@app.get('/admin/users', response_model=List[ManagedUserOut])
def list_users(_: User = Depends(require_capability('user.view'))):
    with Session(engine) as session:
        users = session.exec(select(User).order_by(User.id)).all()
        return [managed_user_payload(u) for u in users]

@app.get('/admin/audit-logs', response_model=List[AuditLogOut])
def list_audit_logs(user: User = Depends(require_capability('audit.view'))):
    with Session(engine) as session:
        rows = session.exec(select(AuditLog).order_by(AuditLog.id.desc()).limit(200)).all()
        return [audit_log_payload(row) for row in rows]

@app.post('/admin/users', response_model=ManagedUserOut)
def create_user(payload: ManagedUserCreate, actor: User = Depends(require_capability('user.create'))):
    username = (payload.username or '').strip()
    display_name = (payload.displayName or '').strip() or username
    password = payload.password or ''
    validate_new_password(password)
    role = validate_role(payload.role) or 'viewer'
    if not username:
        raise HTTPException(status_code=400, detail='用户名不能为空')
    with Session(engine) as session:
        exists = session.exec(select(User).where(User.username == username)).first()
        if exists:
            raise HTTPException(status_code=409, detail='用户名已存在')
        member_id = resolve_user_member_id(session, payload.memberId)
        user = User(
            username=username,
            display_name=display_name,
            role=role,
            is_active=bool(payload.isActive),
            member_id=member_id,
            email=(payload.email or '').strip() or None,
            phone=(payload.phone or '').strip() or None,
            password_hash=hash_password(password),
        )
        session.add(user)
        write_audit_log(session, actor, 'user.create', target_type='user', target_id=username, target_label=display_name or username, detail={'role': role, 'memberId': member_id, 'isActive': bool(payload.isActive)})
        session.commit()
        session.refresh(user)
        return managed_user_payload(user)

@app.put('/admin/users/{user_id}', response_model=ManagedUserOut)
def update_user(user_id: int, payload: ManagedUserUpdate, current: User = Depends(require_capability('user.edit_role'))):
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(404, '用户不存在')
        before = managed_user_payload(user)
        if user.username == 'admin' and payload.role and payload.role != 'super_admin':
            raise HTTPException(status_code=400, detail='内置 admin 必须保留超级管理员角色')
        if current.id == user.id and payload.isActive is False:
            raise HTTPException(status_code=400, detail='不能停用当前登录账号')
        if payload.role is not None:
            user.role = validate_role(payload.role)
        if payload.displayName is not None:
            user.display_name = payload.displayName.strip() or user.username
        if 'memberId' in payload.model_fields_set:
            user.member_id = resolve_user_member_id(session, payload.memberId)
        if payload.email is not None:
            user.email = payload.email.strip() or None
        if payload.phone is not None:
            user.phone = payload.phone.strip() or None
        if payload.isActive is not None:
            user.is_active = bool(payload.isActive)
        user.updated_at = datetime.now(timezone.utc).isoformat()
        after = managed_user_payload(user)
        changed = {
            key: {'before': before.get(key), 'after': after.get(key)}
            for key in ['displayName', 'role', 'memberId', 'email', 'phone', 'isActive']
            if before.get(key) != after.get(key)
        }
        session.add(user)
        write_audit_log(session, current, 'user.update', target_type='user', target_id=user.id, target_label=user.username, detail=changed)
        session.commit()
        session.refresh(user)
        return managed_user_payload(user)

@app.post('/admin/users/{user_id}/disable', response_model=ManagedUserOut)
def disable_user(user_id: int, current: User = Depends(require_capability('user.disable'))):
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(404, '用户不存在')
        if current.id == user.id:
            raise HTTPException(status_code=400, detail='不能停用当前登录账号')
        user.is_active = False
        user.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(user)
        write_audit_log(session, current, 'user.disable', target_type='user', target_id=user.id, target_label=user.username)
        session.commit()
        session.refresh(user)
        return managed_user_payload(user)

@app.post('/admin/users/{user_id}/enable', response_model=ManagedUserOut)
def enable_user(user_id: int, user: User = Depends(require_capability('user.disable'))):
    with Session(engine) as session:
        target = session.get(User, user_id)
        if not target:
            raise HTTPException(404, '用户不存在')
        target.is_active = True
        target.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(target)
        write_audit_log(session, user, 'user.enable', target_type='user', target_id=target.id, target_label=target.username)
        session.commit()
        session.refresh(target)
        return managed_user_payload(target)

@app.post('/admin/users/{user_id}/reset-password')
def reset_user_password(user_id: int, payload: PasswordResetPayload, actor: User = Depends(require_capability('user.reset_password'))):
    validate_new_password(payload.password)
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(404, '用户不存在')
        user.password_hash = hash_password(payload.password)
        user.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(user)
        write_audit_log(session, actor, 'user.reset_password', target_type='user', target_id=user.id, target_label=user.username)
        session.commit()
        return {'ok': True}

@app.put('/settings')
def update_settings(payload: AppSettings, actor: User = Depends(require_capability('settings.edit_basic'))):
    backup_db('before-settings-update')
    with Session(engine) as session:
        before = get_settings_dict(session)
        result = save_settings_dict(session, payload)
        changed = {
            key: {'before': before.get(key), 'after': result.get(key)}
            for key in result.keys()
            if before.get(key) != result.get(key)
        }
        write_audit_log(session, actor, 'settings.update', target_type='settings', target_id='app', target_label='系统设置', detail=changed)
        session.commit()
        return result

@app.get('/members')
def list_members(user: User = Depends(require_capability('member.view'))):
    with Session(engine) as session:
        visibility = build_member_visibility(session, user)
        scope_ids = None if visibility is None else (visibility.get(VISIBILITY_SCOPE_FULL, set()) | visibility.get(VISIBILITY_SCOPE_BASIC, set()))
        default_visible_fields = resolve_visible_member_fields(session, user)
        members = session.exec(select(Member).order_by(Member.generation, Member.rank_no, Member.id)).all()
        if scope_ids is not None:
            members = [m for m in members if m.id in scope_ids]
        members = [m for m in members if can_view_member_with_visibility(user, m, visibility)]
        by_id = {m.id: m for m in members if m.id is not None}
        result = []
        for m in members:
            scope = member_visibility_scope(m.id, visibility)
            payload = member_to_dict(m, visible_fields=visible_fields_for_scope(default_visible_fields, scope), by_id=by_id, all_members=members)
            result.append(attach_visibility_payload(payload, scope))
        return result

@app.get('/members/{member_id}')
def get_member(member_id: int, user: User = Depends(require_capability('member.view'))):
    with Session(engine) as session:
        m = session.get(Member, member_id)
        if not m:
            raise HTTPException(404, '成员不存在')
        visibility = build_member_visibility(session, user)
        if not can_view_member_with_visibility(user, m, visibility):
            raise HTTPException(status_code=403, detail='当前账号无权访问该成员')
        scope = member_visibility_scope(m.id, visibility)
        default_visible_fields = resolve_visible_member_fields(session, user)
        all_members = session.exec(select(Member)).all()
        if visibility is not None:
            visible_ids = visibility.get(VISIBILITY_SCOPE_FULL, set()) | visibility.get(VISIBILITY_SCOPE_BASIC, set())
            all_members = [x for x in all_members if x.id in visible_ids and can_view_member_with_visibility(user, x, visibility)]
        payload = member_to_dict(m, visible_fields=visible_fields_for_scope(default_visible_fields, scope), by_id={x.id: x for x in all_members if x.id is not None}, all_members=all_members)
        return attach_visibility_payload(payload, scope)

@app.post('/members')
def create_member(payload: MemberCreate, user: User = Depends(require_capability('member.create'))):
    backup_db('before-create')
    data = filter_member_payload_for_user(user, payload, for_create=True)
    if not data.get('name'):
        raise HTTPException(status_code=403, detail='当前账号不可创建成员或缺少必要字段')
    with Session(engine) as session:
        data = resolve_relation_payload(session, data)
        scope_ids = build_member_full_scope(session, user)
        if scope_ids is not None:
            allowed_parent_ids = {pid for pid in [data.get('father_id'), data.get('mother_id')] if pid}
            if allowed_parent_ids:
                if not allowed_parent_ids.intersection(scope_ids):
                    raise HTTPException(status_code=403, detail='当前账号仅可在自己归属分支下新增成员')
            else:
                raise HTTPException(status_code=403, detail='当前账号新增成员时必须挂接到自己归属分支内的父亲或母亲')
        data['spouse_ids'] = encode_spouse_ids_value(data.get('spouse_ids') or [])
        
        # Set primary_family_id if not provided
        if 'primary_family_id' not in data or data['primary_family_id'] is None:
            father_id = data.get('father_id')
            mother_id = data.get('mother_id')
            spouse_ids = parse_spouse_ids_value(data.get('spouse_ids'))
            
            inherited_family_id = None
            if father_id:
                father = session.get(Member, father_id)
                if father and father.primary_family_id:
                    inherited_family_id = father.primary_family_id
            if not inherited_family_id and mother_id:
                mother = session.get(Member, mother_id)
                if mother and mother.primary_family_id:
                    inherited_family_id = mother.primary_family_id
            if not inherited_family_id and spouse_ids:
                first_spouse = session.get(Member, spouse_ids[0])
                if first_spouse and first_spouse.primary_family_id:
                    inherited_family_id = first_spouse.primary_family_id
                    
            if inherited_family_id:
                data['primary_family_id'] = inherited_family_id
            else:
                primary_family = session.exec(select(FamilyGroup).where(FamilyGroup.is_primary == True)).first()
                if primary_family:
                    data['primary_family_id'] = primary_family.id
        
        family_id = data.get('primary_family_id')
        if family_id and not can_edit_family(session, user, family_id):
            raise HTTPException(status_code=403, detail='当前账号无权在此家族中创建成员')
        
        m = Member(**data)
        session.add(m)
        session.commit()
        session.refresh(m)
        
        # 建立多家族关联记录，保持数据同步
        if m.id and m.primary_family_id:
            link = MemberFamilyLink(member_id=m.id, family_id=m.primary_family_id)
            session.add(link)
            
        sync_member_spouse_links(session, m.id, [], parse_spouse_ids_value(m.spouse_ids))
        write_audit_log(session, user, 'member.create', target_type='member', target_id=m.id, target_label=m.name, detail={'fatherName': m.father_name, 'motherName': m.mother_name, 'generation': m.generation})
        session.commit()
        all_members = session.exec(select(Member)).all()
        return member_to_dict(m, all_members=all_members)

@app.get('/member-photos/{filename}')
def get_member_photo(filename: str, user: User = Depends(require_capability('member.view'))):
    target = (PHOTO_DIR / filename).resolve()
    if PHOTO_DIR.resolve() not in target.parents or not target.exists() or not target.is_file():
        raise HTTPException(404, '照片不存在')
    expected_path = f'/api/member-photos/{filename}'
    with Session(engine) as session:
        member = session.exec(select(Member).where(
            (Member.photo_path == expected_path) |
            (Member.photo_path == f'/member-photos/{filename}') |
            (Member.photo_path == filename) |
            (Member.photo_path.like(f'%/{filename}'))
        )).first()
        if not member or not can_view_member_with_visibility(user, member, build_member_visibility(session, user)):
            raise HTTPException(status_code=403, detail='当前账号无权访问该成员照片')
    media_type = detect_image_mime(target.read_bytes()[:512]) or 'application/octet-stream'
    return FileResponse(path=target, media_type=media_type)


@app.post('/members/{member_id}/photo')
def upload_member_photo(member_id: int, file: UploadFile = File(...), user: User = Depends(require_capability('member.edit_profile'))):
    suffix = Path(file.filename or '').suffix.lower()
    validate_photo_upload(file, suffix)
    backup_db(f'before-photo-{member_id}')
    with Session(engine) as session:
        m = session.get(Member, member_id)
        require_member_in_full_scope(session, user, m)
        filename = f'member-{member_id}-{local_timestamp_for_filename()}-{uuid.uuid4().hex[:12]}{suffix}'
        target = PHOTO_DIR / filename
        save_limited_upload(file, target, PHOTO_MAX_BYTES, label='照片')
        m.photo_path = f'/api/member-photos/{filename}'
        m.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(m)
        write_audit_log(session, user, 'member.upload_photo', target_type='member', target_id=m.id, target_label=m.name, detail={'photo': filename})
        session.commit()
        session.refresh(m)
        all_members = session.exec(select(Member)).all()
        return member_to_dict(m, all_members=all_members)

@app.put('/members/{member_id}')
def update_member(member_id: int, payload: MemberUpdate, user: User = Depends(require_capability('member.edit_profile'))):
    backup_db(f'before-update-{member_id}')
    raw_data = payload.model_dump(exclude_unset=True)
    data = filter_member_payload_for_user(user, payload, for_create=False)
    requested_structure = {k: v for k, v in raw_data.items() if k in CORE_RELATION_FIELDS}
    with Session(engine) as session:
        m = session.get(Member, member_id)
        require_member_in_full_scope(session, user, m)
        if m.primary_family_id and not can_edit_family(session, user, m.primary_family_id):
            raise HTTPException(status_code=403, detail='当前账号无权编辑此成员所属家族的资料')
        if 'primary_family_id' in data:
            new_family_id = data['primary_family_id']
            if new_family_id and new_family_id != m.primary_family_id:
                if not can_edit_family(session, user, new_family_id):
                    raise HTTPException(status_code=403, detail='当前账号无权将成员转移到该家族')
        review_request = None
        if requested_structure and 'member.edit_core_relation' not in get_user_capabilities(user):
            review_request = create_member_review_request_if_changed(session, user, m, requested_structure)
        if not data:
            if review_request:
                session.commit()
                return {'ok': True, 'pendingReview': review_request_payload(review_request), 'member': member_to_dict(m)}
            raise HTTPException(status_code=403, detail='当前账号无可编辑字段')
        old_spouse_ids = parse_spouse_ids_value(m.spouse_ids)
        data = resolve_relation_payload(session, data, current_member_id=member_id)
        if 'spouse_ids' in data:
            data['spouse_ids'] = encode_spouse_ids_value(data.get('spouse_ids') or [])
        before = {key: getattr(m, key, None) for key in data.keys()}
        for k, v in data.items():
            setattr(m, k, v)
        m.updated_at = datetime.now(timezone.utc).isoformat()
        if 'spouse_ids' in data:
            sync_member_spouse_links(session, m.id, old_spouse_ids, parse_spouse_ids_value(m.spouse_ids))
        if 'primary_family_id' in data:
            new_fam_id = data['primary_family_id']
            old_fam_id = before.get('primary_family_id')
            if old_fam_id != new_fam_id:
                if old_fam_id:
                    old_links = session.exec(select(MemberFamilyLink).where(
                        MemberFamilyLink.member_id == m.id,
                        MemberFamilyLink.family_id == old_fam_id
                    )).all()
                    for l in old_links:
                        session.delete(l)
                if new_fam_id:
                    existing = session.exec(select(MemberFamilyLink).where(
                        MemberFamilyLink.member_id == m.id,
                        MemberFamilyLink.family_id == new_fam_id
                    )).first()
                    if not existing:
                        link = MemberFamilyLink(member_id=m.id, family_id=new_fam_id)
                        session.add(link)
        after = {key: getattr(m, key, None) for key in data.keys()}
        changed = {
            key: {'before': before.get(key), 'after': after.get(key)}
            for key in data.keys()
            if before.get(key) != after.get(key)
        }
        audit_detail = classify_member_change_detail(changed)
        if review_request:
            audit_detail['pendingReviewId'] = review_request.id
        session.add(m)
        write_audit_log(session, user, 'member.update', target_type='member', target_id=m.id, target_label=m.name, detail=audit_detail)
        session.commit()
        session.refresh(m)
        all_members = session.exec(select(Member)).all()
        result = member_to_dict(m, all_members=all_members)
        if review_request:
            result['pendingReview'] = review_request_payload(review_request)
        return result

@app.delete('/members/{member_id}')
def delete_member(member_id: int, user: User = Depends(require_capability('member.delete'))):
    backup_db(f'before-delete-{member_id}')
    with Session(engine) as session:
        m = session.get(Member, member_id)
        require_member_in_full_scope(session, user, m)
        ensure_member_can_be_deleted(session, member_id)
        sync_member_spouse_links(session, m.id, parse_spouse_ids_value(m.spouse_ids), [])
        
        # 清理多家族关联表中的关联记录，避免脏数据残留
        links = session.exec(select(MemberFamilyLink).where(MemberFamilyLink.member_id == member_id)).all()
        for link in links:
            session.delete(link)
            
        write_audit_log(session, user, 'member.delete', target_type='member', target_id=m.id, target_label=m.name, detail={'generation': m.generation, 'fatherName': m.father_name, 'motherName': m.mother_name})
        session.delete(m)
        session.commit()
        return {'ok': True}

@app.get('/families')
def get_families(user: User = Depends(require_capability('family.view'))):
    with Session(engine) as session:
        families = session.exec(select(FamilyGroup).where(FamilyGroup.is_active == True)).all()
        return [{
            'id': f.id,
            'name': f.name,
            'surname': f.surname,
            'siteTitle': f.site_title,
            'coverKicker': f.cover_kicker,
            'subtitle': f.subtitle,
            'description': f.description,
            'rootMemberId': f.root_member_id,
            'primaryLine': f.primary_line,
            'isPrimary': f.is_primary,
            'isActive': f.is_active,
            'sortOrder': f.sort_order,
        } for f in families]

@app.get('/families/{family_id}')
def get_family(family_id: int, user: User = Depends(require_capability('family.view'))):
    with Session(engine) as session:
        family = session.get(FamilyGroup, family_id)
        if not family:
            raise HTTPException(status_code=404, detail='家族不存在')
        
        # Count members in this family
        member_count = len(session.exec(select(Member).where(Member.primary_family_id == family_id)).all())
        
        return {
            'id': family.id,
            'name': family.name,
            'surname': family.surname,
            'siteTitle': family.site_title,
            'coverKicker': family.cover_kicker,
            'subtitle': family.subtitle,
            'description': family.description,
            'rootMemberId': family.root_member_id,
            'primaryLine': family.primary_line,
            'isPrimary': family.is_primary,
            'isActive': family.is_active,
            'sortOrder': family.sort_order,
            'memberCount': member_count,
            'createdAt': family.created_at,
            'updatedAt': family.updated_at,
        }

@app.put('/families/{family_id}')
def update_family(family_id: int, payload: Dict[str, Any], user: User = Depends(get_current_user)):
    with Session(engine) as session:
        # Check family-level edit permission
        if not can_edit_family(session, user, family_id):
            raise HTTPException(status_code=403, detail='当前账号无权编辑该家族')
        
        family = session.get(FamilyGroup, family_id)
        if not family:
            raise HTTPException(status_code=404, detail='家族不存在')
        
        # Update allowed fields
        allowed_fields = {'name', 'surname', 'site_title', 'cover_kicker', 'subtitle', 'description', 'root_member_id', 'primary_line', 'sort_order'}
        for key, value in payload.items():
            snake_key = ''.join(['_' + c.lower() if c.isupper() else c for c in key]).lstrip('_')
            if snake_key in allowed_fields:
                setattr(family, snake_key, value)
        
        family.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(family)
        
        write_audit_log(session, user, 'family.edit', target_type='family', target_id=family.id, target_label=family.name, detail=payload)
        session.commit()
        session.refresh(family)
        
        return {
            'id': family.id,
            'name': family.name,
            'surname': family.surname,
            'siteTitle': family.site_title,
            'coverKicker': family.cover_kicker,
            'subtitle': family.subtitle,
            'description': family.description,
            'rootMemberId': family.root_member_id,
            'primaryLine': family.primary_line,
            'isPrimary': family.is_primary,
            'isActive': family.is_active,
            'sortOrder': family.sort_order,
        }

@app.get('/families/{family_id}/users')
def get_family_users(family_id: int, user: User = Depends(require_capability('family.view'))):
    """Get all users with roles in this family."""
    with Session(engine) as session:
        family = session.get(FamilyGroup, family_id)
        if not family:
            raise HTTPException(status_code=404, detail='家族不存在')
        
        roles = session.exec(
            select(UserFamilyRole).where(UserFamilyRole.family_id == family_id)
        ).all()
        
        result = []
        for role in roles:
            user_obj = session.get(User, role.user_id)
            if user_obj:
                result.append({
                    'userId': user_obj.id,
                    'username': user_obj.username,
                    'displayName': user_obj.display_name,
                    'role': role.role,
                    'createdAt': role.created_at,
                })
        
        return result

@app.post('/families/{family_id}/users')
def add_family_user(family_id: int, payload: Dict[str, Any], user: User = Depends(get_current_user)):
    """Assign a user to this family with a specific role."""
    with Session(engine) as session:
        if not can_edit_family(session, user, family_id):
            raise HTTPException(status_code=403, detail='当前账号无权管理该家族的用户权限')
        
        family = session.get(FamilyGroup, family_id)
        if not family:
            raise HTTPException(status_code=404, detail='家族不存在')
        
        target_user_id = payload.get('userId')
        role = payload.get('role', 'viewer')
        
        if not target_user_id:
            raise HTTPException(status_code=400, detail='缺少 userId 参数')
        
        target_user = session.get(User, target_user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail='用户不存在')
        
        # Check if already exists
        existing = session.exec(
            select(UserFamilyRole)
            .where(UserFamilyRole.user_id == target_user_id)
            .where(UserFamilyRole.family_id == family_id)
        ).first()
        
        if existing:
            existing.role = role
            existing.updated_at = datetime.now(timezone.utc).isoformat()
            session.add(existing)
        else:
            new_role = UserFamilyRole(
                user_id=target_user_id,
                family_id=family_id,
                role=role,
            )
            session.add(new_role)
        
        write_audit_log(session, user, 'family.assign_user', target_type='family', target_id=family.id, target_label=family.name, detail={'targetUserId': target_user_id, 'role': role})
        session.commit()
        
        return {'ok': True}

@app.delete('/families/{family_id}/users/{user_id}')
def remove_family_user(family_id: int, user_id: int, user: User = Depends(get_current_user)):
    """Remove a user's role from this family."""
    with Session(engine) as session:
        if not can_edit_family(session, user, family_id):
            raise HTTPException(status_code=403, detail='当前账号无权管理该家族的用户权限')
        
        role = session.exec(
            select(UserFamilyRole)
            .where(UserFamilyRole.user_id == user_id)
            .where(UserFamilyRole.family_id == family_id)
        ).first()
        
        if not role:
            raise HTTPException(status_code=404, detail='该用户在此家族中没有角色')
        
        session.delete(role)
        write_audit_log(session, user, 'family.remove_user', target_type='family', target_id=family_id, target_label=str(family_id), detail={'targetUserId': user_id})
        session.commit()
        
        return {'ok': True}

@app.get('/families/{family_id}/tree')
def get_family_tree(family_id: int, user: User = Depends(require_capability('tree.view'))):
    with Session(engine) as session:
        family = session.get(FamilyGroup, family_id)
        if not family:
            raise HTTPException(status_code=404, detail='家族不存在')
        
        visibility = build_member_visibility(session, user)
        default_visible_fields = resolve_visible_member_fields(session, user)
        
        # Filter members by primary_family_id or family link
        linked_member_ids = session.exec(
            select(MemberFamilyLink.member_id).where(MemberFamilyLink.family_id == family_id)
        ).all()
        if linked_member_ids:
            all_members = session.exec(
                select(Member).where(
                    (Member.primary_family_id == family_id) | (Member.id.in_(linked_member_ids))
                )
            ).all()
        else:
            all_members = session.exec(
                select(Member).where(Member.primary_family_id == family_id)
            ).all()
        
        if visibility is None:
            visible_ids = {m.id for m in all_members if m.id is not None}
            tree_nodes = build_tree(session, allowed_ids=visible_ids, visible_fields=default_visible_fields)
            return {'nodes': tree_nodes}
        
        visible_ids = {m.id for m in all_members if m.id is not None and can_view_member_with_visibility(user, m, visibility)}
        visible_fields_by_id = {}
        visibility_scope_by_id = {}
        for member_id in visible_ids:
            scope = member_visibility_scope(member_id, visibility)
            visible_fields_by_id[member_id] = visible_fields_for_scope(default_visible_fields, scope)
            visibility_scope_by_id[member_id] = scope
        
        tree_nodes = build_tree(
            session,
            allowed_ids=visible_ids,
            visible_fields=default_visible_fields,
            visible_fields_by_id=visible_fields_by_id,
            visibility_scope_by_id=visibility_scope_by_id,
        )
        return {'nodes': tree_nodes}

@app.get('/members/{member_id}/ancestry')
def get_member_ancestry(
    member_id: int,
    mode: str = 'four-line',
    generations: int = 3,
    user: User = Depends(require_capability('member.view'))
):
    with Session(engine) as session:
        member = session.get(Member, member_id)
        if not member:
            raise HTTPException(status_code=404, detail='成员不存在')
        
        all_members = session.exec(select(Member)).all()
        by_id = {m.id: m for m in all_members if m.id is not None}
        
        def trace_line(start_id: int, parent_getter, max_gen: int):
            line = []
            current_id = start_id
            for _ in range(max_gen):
                if current_id is None or current_id not in by_id:
                    break
                current = by_id[current_id]
                line.append(member_to_dict(current, include_relations=False, by_id=by_id, all_members=all_members))
                current_id = parent_getter(current)
            return line
        
        result = {
            'member': member_to_dict(member, include_relations=False, by_id=by_id, all_members=all_members),
            'lines': {}
        }
        
        if mode == 'four-line':
            result['lines']['paternal'] = trace_line(member.father_id, lambda m: m.father_id, generations)
            result['lines']['maternal'] = trace_line(member.mother_id, lambda m: m.father_id, generations)
            if member.father_id and member.father_id in by_id:
                father = by_id[member.father_id]
                result['lines']['paternal_maternal'] = trace_line(father.mother_id, lambda m: m.father_id, generations)
            if member.mother_id and member.mother_id in by_id:
                mother = by_id[member.mother_id]
                result['lines']['maternal_maternal'] = trace_line(mother.mother_id, lambda m: m.father_id, generations)
        
        return result

@app.get('/tree')
def tree(user: User = Depends(require_capability('tree.view'))):
    with Session(engine) as session:
        visibility = build_member_visibility(session, user)
        default_visible_fields = resolve_visible_member_fields(session, user)
        all_members = session.exec(select(Member)).all()
        if visibility is None:
            visible_ids = {m.id for m in all_members if m.id is not None}
            allowed_ids = None
            return build_tree(session, allowed_ids, visible_fields=default_visible_fields)

        visible_ids = {m.id for m in all_members if m.id is not None and can_view_member_with_visibility(user, m, visibility)}
        visible_fields_by_id = {}
        visibility_scope_by_id = {}
        for member_id in visible_ids:
            scope = member_visibility_scope(member_id, visibility)
            visible_fields_by_id[member_id] = visible_fields_for_scope(default_visible_fields, scope)
            visibility_scope_by_id[member_id] = scope
        return build_tree(
            session,
            allowed_ids=visible_ids,
            visible_fields=default_visible_fields,
            visible_fields_by_id=visible_fields_by_id,
            visibility_scope_by_id=visibility_scope_by_id,
        )

@app.post('/import/excel')
def upload_excel(file: UploadFile = File(...), user: User = Depends(require_capability('member.import'))):
    backup_db('before-import')
    filename = file.filename or ''
    suffix = Path(filename).suffix.lower()
    if suffix != '.xlsx':
        raise HTTPException(status_code=400, detail='仅支持 .xlsx Excel 文件导入')
    tmp = DATA_DIR / f'upload-{local_timestamp_for_filename()}-{uuid.uuid4().hex[:12]}.xlsx'
    try:
        save_limited_upload(file, tmp, EXCEL_MAX_BYTES, label='Excel文件')
        count = import_excel(str(tmp), replace=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    with Session(engine) as audit_session:
        write_audit_log(audit_session, user, 'member.import_excel', target_type='import', target_id=tmp.name, target_label=file.filename or tmp.name, detail={'count': count})
        audit_session.commit()
    return {'ok': True, 'count': count}

@app.get('/import/template')
def download_import_template(_: User = Depends(require_capability('member.import'))):
    path = ensure_import_template()
    return FileResponse(
        path=path,
        filename='家谱成员导入样表.xlsx',
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.post('/admin/import-default')
def import_default_disabled(_: User = Depends(require_capability('member.import'))):
    raise HTTPException(410, '已取消直接导入内置数据，请先下载样表，填写后上传 Excel 导入')

@app.post('/admin/backup')
def make_backup(user: User = Depends(require_capability('backup.create'))):
    result = backup_db('manual')
    with Session(engine) as audit_session:
        write_audit_log(audit_session, user, 'backup.create', target_type='backup', target_id=result.get('path'), target_label=result.get('path'))
        audit_session.commit()
    return result

@app.get('/admin/backups')
def backups(_: User = Depends(require_capability('backup.view'))):
    prune_auto_backups()
    items = sorted(BACKUP_DIR.glob('family-*.db'), key=backup_sort_key, reverse=True)
    result = []
    for p in items:
        stat = p.stat()
        meta = classify_backup_file(p)
        result.append({
            'file': p.name,
            'path': str(p),
            'size': stat.st_size,
            'mtime': local_iso_from_timestamp(stat.st_mtime),
            'createdAt': backup_created_at(p),
            'timezone': str(LOCAL_TIMEZONE),
            'downloadUrl': f"/api/admin/backups/{quote(p.name)}/download",
            'canDelete': True,
            'deleteHint': '可手动删除；自动保留策略只清理普通自动备份' if meta.get('retentionProtected') else '可手动删除；超过最近30个普通自动备份时会自动清理',
            **meta,
        })
    return result

@app.get('/admin/backups/{filename}/download')
def download_backup(filename: str, _: User = Depends(require_capability('backup.download'))):
    target = (BACKUP_DIR / filename).resolve()
    if BACKUP_DIR.resolve() not in target.parents or not target.exists():
        raise HTTPException(404, '备份不存在')
    return FileResponse(path=target, filename=target.name, media_type='application/octet-stream')

@app.delete('/admin/backups/{filename}')
def delete_backup(filename: str, user: User = Depends(require_capability('backup.delete'))):
    target = (BACKUP_DIR / filename).resolve()
    if BACKUP_DIR.resolve() not in target.parents or not target.exists():
        raise HTTPException(404, '备份不存在')
    target.unlink()
    with Session(engine) as audit_session:
        write_audit_log(audit_session, user, 'backup.delete', target_type='backup', target_id=filename, target_label=filename)
        audit_session.commit()
    return {'ok': True, 'deleted': filename}

@app.post('/admin/backups/upload')
async def upload_backup(file: UploadFile, user: User = Depends(require_capability('backup.restore'))):
    """上传备份文件（需要恢复权限）"""
    if not file.filename or not file.filename.endswith('.db'):
        raise HTTPException(400, '仅支持 .db 格式的 SQLite 备份文件')
    
    # 生成安全的文件名（带时间戳和原始文件名）
    safe_filename = f'uploaded-{local_timestamp_for_filename()}-{file.filename}'
    target_path = (BACKUP_DIR / safe_filename).resolve()
    
    # 确保路径安全
    if BACKUP_DIR.resolve() not in target_path.parents:
        raise HTTPException(400, '非法的文件路径')
    
    # 保存上传的文件
    try:
        content = await file.read()
        with open(target_path, 'wb') as f:
            f.write(content)
        
        # 验证是否为有效的 SQLite 文件
        validate_sqlite_backup_file(target_path)
        
        # 记录审计日志
        with Session(engine) as audit_session:
            write_audit_log(
                audit_session, user, 'backup.upload',
                target_type='backup', target_id=safe_filename, target_label=safe_filename,
                detail={'originalFilename': file.filename, 'size': len(content)}
            )
            audit_session.commit()
        
        return {
            'ok': True,
            'filename': safe_filename,
            'originalFilename': file.filename,
            'size': len(content)
        }
    except HTTPException:
        # 如果验证失败，删除已上传的文件
        target_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        target_path.unlink(missing_ok=True)
        raise HTTPException(500, f'上传备份失败: {str(exc)}') from exc

@app.post('/admin/restore/{filename}')
def restore(filename: str, user: User = Depends(require_capability('backup.restore'))):
    target = (BACKUP_DIR / filename).resolve()
    if BACKUP_DIR.resolve() not in target.parents or not target.exists():
        raise HTTPException(404, '备份不存在')
    validate_sqlite_backup_file(target)
    snapshot = backup_db('before-restore')
    db_path = sqlite_path()
    staging = DATA_DIR / f'restore-{local_timestamp_for_filename()}-{uuid.uuid4().hex[:12]}.db'
    try:
        shutil.copy2(target, staging)
        validate_sqlite_backup_file(staging)
        engine.dispose()
        os.replace(staging, db_path)
        init_db()
    except Exception as exc:
        engine.dispose()
        try:
            safety_path = Path(snapshot.get('path', ''))
            if safety_path.exists():
                os.replace(safety_path, db_path)
                init_db()
        except Exception:
            pass
        try:
            staging.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=500, detail='恢复备份失败，已尝试回滚到恢复前保护备份') from exc
    with Session(engine) as audit_session:
        write_audit_log(audit_session, user, 'backup.restore', target_type='backup', target_id=filename, target_label=filename, detail={'safetyBackup': snapshot.get('file')})
        audit_session.commit()
    return {'ok': True, 'restored': filename, 'safetyBackup': snapshot}
