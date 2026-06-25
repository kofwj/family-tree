import backend.main as main
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

from backend.database import RUNNING_IN_CONTAINER, is_strong_password_value

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
    if main.DATABASE_URL.startswith('sqlite:////'):
        return Path('/' + main.DATABASE_URL.removeprefix('sqlite:////'))
    if main.DATABASE_URL.startswith('sqlite:///'):
        return Path(main.DATABASE_URL.removeprefix('sqlite:///'))
    return main.DATA_DIR / 'family.db'

from backend.database import (
    RUNNING_IN_CONTAINER, connect_args, get_db, JWT_ALG,
    PHOTO_MAX_BYTES, LOGIN_RATE_LIMIT_MAX,
    LOGIN_RATE_LIMIT_WINDOW_SECONDS, LOGIN_RATE_LIMIT_LOCK_SECONDS
)
from backend.models import (
    Member, User, FamilyGroup, MemberFamilyLink, UserFamilyRole,
    AuditLog, SourceRecord, Citation, ReviewRequest, SiteSetting
)
from backend.schemas import (
    MemberCreate, MemberUpdate, Token, CurrentUserOut, ManagedUserOut,
    ManagedUserCreate, ManagedUserUpdate, PasswordResetPayload,
    AuditLogOut, SourceIn, CitationIn, ReviewRejectPayload,
    FieldVisibilityTemplateConfig, AppSettings
)
from backend.auth import (
    ROLE_LABELS, ROLE_CAPABILITIES, oauth2_scheme, hash_password,
    verify_password, get_user_capabilities, get_current_user,
    require_capability
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

_SQL_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_ALLOWED_COLUMN_TYPES = {'TEXT', 'INTEGER', 'REAL', 'BLOB', 'NUMERIC'}

def _validate_sql_identifier(name: str) -> str:
    if not isinstance(name, str) or not _SQL_IDENTIFIER_RE.match(name):
        raise ValueError(f'非法的 SQL 标识符: {name!r}')
    return name

def migrate_sqlite_table_columns(table_name: str, columns: Dict[str, str]):
    if not main.DATABASE_URL.startswith('sqlite'):
        return
    db_path = sqlite_path()
    if not db_path.exists():
        return
    # 校验标识符，防止 DDL 注入（SQLite 无法对标识符做参数化绑定）
    _validate_sql_identifier(table_name)
    for column, column_type in columns.items():
        _validate_sql_identifier(column)
        base_type = column_type.strip().split()[0].upper()
        if base_type not in _ALLOWED_COLUMN_TYPES:
            raise ValueError(f'不支持的列类型: {column_type!r}')
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

def _load_auto_organize_seed() -> Optional[Dict[str, Any]]:
    """Load the family-organization seed data from an external JSON file.

    The data (specific family names / real person names) lives outside the
    source code. Path can be overridden via AUTO_ORGANIZE_SEED_FILE; defaults to
    backend/data_seed/auto_organize.json. Returns None if the file is absent.
    """
    seed_path = os.getenv('AUTO_ORGANIZE_SEED_FILE')
    if seed_path:
        path = Path(seed_path)
    else:
        path = Path(os.path.dirname(__file__)) / 'data_seed' / 'auto_organize.json'
    if not path.exists():
        print(f"[Startup] Auto-organize seed file not found at {path}; skipping organization.")
        return None
    try:
        with path.open(encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[Startup] Failed to read auto-organize seed file {path}: {exc}; skipping.")
        return None


def run_auto_organization(session: Session):
    # Check if database has members and they are all still in a single family (or unassigned)
    members = session.exec(select(Member)).all()
    distinct_families = {m.primary_family_id for m in members if m.primary_family_id is not None}
    if not (len(members) > 0 and len(distinct_families) <= 1):
        return

    seed = _load_auto_organize_seed()
    if not seed:
        return

    families = seed.get('families', [])
    family_roots = {int(k): v for k, v in (seed.get('family_roots', {}) or {}).items()}
    member_name_primary_family = seed.get('member_primary_family', {}) or {}
    secondary_links = seed.get('secondary_links', []) or []

    # 1 & 2. Create/update family groups from seed
    for fam in families:
        fid = fam.get('id')
        if fid is None:
            continue
        existing = session.get(FamilyGroup, fid)
        if existing:
            # Only the primary (id-based) family is renamed in-place (was family 1).
            if fam.get('is_primary'):
                existing.name = fam.get('name', existing.name)
                existing.surname = fam.get('surname', existing.surname)
                existing.site_title = fam.get('site_title', existing.site_title)
                existing.cover_kicker = fam.get('cover_kicker', existing.cover_kicker)
                existing.subtitle = fam.get('subtitle', existing.subtitle)
                existing.is_primary = True
                session.add(existing)
        else:
            fg = FamilyGroup(
                id=fid,
                name=fam.get('name', ''),
                surname=fam.get('surname'),
                site_title=fam.get('site_title'),
                cover_kicker=fam.get('cover_kicker'),
                subtitle=fam.get('subtitle'),
                is_primary=bool(fam.get('is_primary', False)),
                is_active=True,
                sort_order=0,
                primary_line='paternal'
            )
            session.add(fg)
    session.commit()

    # Reload members and build name-to-member mapping
    members = session.exec(select(Member)).all()
    name_to_member = {m.name: m for m in members if m.name}

    # Update root member IDs dynamically by name
    for fid, root_name in family_roots.items():
        fg = session.get(FamilyGroup, fid)
        rm = name_to_member.get(root_name)
        if fg and rm:
            fg.root_member_id = rm.id
            session.add(fg)

    # 4. Clear existing links
    existing_links = session.exec(select(MemberFamilyLink)).all()
    for link in existing_links:
        session.delete(link)

    # 5. Set primary_family_id and insert primary family links
    for name, fid in member_name_primary_family.items():
        m = name_to_member.get(name)
        if m:
            m.primary_family_id = fid
            session.add(m)
            link = MemberFamilyLink(member_id=m.id, family_id=fid, relation_type='primary', is_primary=True)
            session.add(link)

    # 6. Insert secondary links (spouses marrying into other families)
    for entry in secondary_links:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            continue
        name, fid = entry
        m = name_to_member.get(name)
        if m:
            link = MemberFamilyLink(member_id=m.id, family_id=fid, relation_type='secondary', is_primary=False)
            session.add(link)

    session.commit()

def heal_unlinked_relations(session: Session):
    members = session.exec(select(Member)).all()
    by_name: Dict[str, List[Member]] = {}
    for m in members:
        nm = normalize_name_value(m.name)
        if nm:
            by_name.setdefault(nm, []).append(m)

    healed_count = 0
    for m in members:
        changed = False
        family_id = m.primary_family_id

        # 1. Heal father relation
        if m.father_name and not m.father_id:
            cands = [x for x in by_name.get(normalize_name_value(m.father_name), []) if x.primary_family_id == family_id]
            father = pick_best_parent(cands, m.generation)
            if father and father.id:
                m.father_id = father.id
                changed = True
                
        # 2. Heal mother relation
        if m.mother_name and not m.mother_id:
            cands = [x for x in by_name.get(normalize_name_value(m.mother_name), []) if x.primary_family_id == family_id]
            mother = pick_best_parent(cands, m.generation)
            if mother and mother.id:
                m.mother_id = mother.id
                changed = True

        # 3. Heal spouse relations
        spouse_ids = parse_spouse_ids_value(m.spouse_ids)
        if m.spouse_name and not spouse_ids:
            spouse_members = []
            for sp_name in split_relation_names(m.spouse_name):
                cands = [x for x in by_name.get(sp_name, []) if x.primary_family_id == family_id]
                best_sp = pick_best_spouse(cands, m.generation, exclude_id=m.id)
                if best_sp:
                    spouse_members.append(best_sp)
            uniq_ids = []
            for sp in spouse_members:
                if sp.id and sp.id != m.id and sp.id not in uniq_ids:
                    uniq_ids.append(sp.id)
            if uniq_ids:
                m.spouse_ids = encode_spouse_ids_value(uniq_ids)
                changed = True

        if changed:
            session.add(m)
            healed_count += 1

    if healed_count > 0:
        session.commit()
        # Also sync links
        for m in members:
            sync_member_spouse_links(session, m.id, [], parse_spouse_ids_value(m.spouse_ids))
        print(f"[Heal] Automatically healed {healed_count} unlinked member relationships.")

def init_db():
    from sqlalchemy import inspect
    from alembic.config import Config
    from alembic import command

    # Run programmatic Alembic migrations on startup
    inspector = inspect(main.engine)
    tables = inspector.get_table_names()
    
    # Locate alembic.ini in the same directory as helpers.py (backend/)
    alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'alembic.ini'))
    alembic_cfg = Config(alembic_ini_path)
    
    # Check if we have existing tables but no alembic history
    if "member" in tables and "alembic_version" not in tables:
        command.stamp(alembic_cfg, "ba124bb415d6")
    
    # Run all pending migrations
    command.upgrade(alembic_cfg, "head")

    migrate_sqlite_member_columns()
    migrate_sqlite_user_columns()
    migrate_sqlite_audit_log_columns()
    with Session(main.engine) as session:
        ensure_default_family_group(session)
        ensure_member_primary_family(session)
        
        auto_org = os.getenv('AUTO_ORGANIZE_ON_STARTUP', 'false').lower() == 'true'
        if auto_org:
            print("[Startup] Auto organization and healing enabled by environment variable.")
            run_auto_organization(session)
            heal_unlinked_relations(session)
        else:
            print("[Startup] Auto organization and healing are disabled by default.")
            
        ensure_default_admin(session)

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
            admin.password_hash = hash_password(main.ADMIN_PASSWORD)
        session.add(admin)
        session.commit()
        return admin
    admin = User(
        username='admin',
        display_name='系统管理员',
        role='super_admin',
        is_active=True,
        password_hash=hash_password(main.ADMIN_PASSWORD),
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin

def create_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=24)
    return jwt.encode({'sub': user.username, 'uid': user.id, 'role': user.role, 'exp': exp}, main.JWT_SECRET, algorithm=JWT_ALG)

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
        raise HTTPException(status_code=400, detail=f'密码至少需要 {main.PASSWORD_MIN_LENGTH} 位，且必须包含字母和数字，不能包含空白字符')


def login_rate_limit_key(request: Request, username: str) -> str:
    forwarded_for = request.headers.get('x-forwarded-for', '')
    ip = forwarded_for.split(',', 1)[0].strip() or (request.client.host if request.client else 'unknown')
    return f'{ip}:{(username or "").strip().lower()}'


# NOTE: LOGIN_ATTEMPTS is an in-process dict. It is correct for the current
# single-worker uvicorn deployment (see backend/Dockerfile). If you ever run
# multiple workers (uvicorn --workers N / gunicorn), each worker keeps its own
# copy and the effective limit becomes N times higher — switch to a shared
# store (Redis / database) before scaling out.
# Hard cap on tracked keys so a flood of random usernames can't grow memory
# without bound; when exceeded we drop the oldest (earliest first_attempt) entries.
LOGIN_ATTEMPTS_MAX_KEYS = 5000  # 降低上限，从 10000 减少到 5000
LOGIN_ATTEMPTS_LAST_PRUNE = 0  # 上次清理的时间戳
LOGIN_ATTEMPTS_PRUNE_INTERVAL = 60  # 每 60 秒强制清理一次


def _prune_login_attempts(now: float):
    """
    移除过期条目，如果仍超过上限则删除最旧的条目。
    改进：添加定期强制清理机制，防止内存耗尽。
    """
    attempts = main.LOGIN_ATTEMPTS
    expired = [
        k for k, row in attempts.items()
        if now - row.get('first_attempt_at', now) > LOGIN_RATE_LIMIT_WINDOW_SECONDS
        and not (row.get('locked_until', 0) and now < row['locked_until'])
    ]
    for k in expired:
        attempts.pop(k, None)
    if len(attempts) > LOGIN_ATTEMPTS_MAX_KEYS:
        # Drop oldest entries (by first_attempt_at) down to the cap.
        ordered = sorted(attempts.items(), key=lambda kv: kv[1].get('first_attempt_at', 0))
        for k, _ in ordered[:len(attempts) - LOGIN_ATTEMPTS_MAX_KEYS]:
            attempts.pop(k, None)


def check_login_rate_limit(request: Request, username: str):
    global LOGIN_ATTEMPTS_LAST_PRUNE
    now = time.monotonic()

    # 定期强制清理：即使没有登录失败也定期清理过期条目
    if now - LOGIN_ATTEMPTS_LAST_PRUNE > LOGIN_ATTEMPTS_PRUNE_INTERVAL:
        _prune_login_attempts(now)
        LOGIN_ATTEMPTS_LAST_PRUNE = now

    key = login_rate_limit_key(request, username)
    row = main.LOGIN_ATTEMPTS.get(key)
    if not row:
        return
    if now - row.get('first_attempt_at', now) > LOGIN_RATE_LIMIT_WINDOW_SECONDS:
        main.LOGIN_ATTEMPTS.pop(key, None)
        return
    locked_until = row.get('locked_until', 0)
    if locked_until and now < locked_until:
        retry_after = max(1, int(locked_until - now))
        raise HTTPException(status_code=429, detail=f'登录失败次数过多，请 {retry_after} 秒后再试', headers={'Retry-After': str(retry_after)})


def record_login_failure(request: Request, username: str):
    now = time.monotonic()
    key = login_rate_limit_key(request, username)
    row = main.LOGIN_ATTEMPTS.get(key)
    if not row or now - row.get('first_attempt_at', now) > LOGIN_RATE_LIMIT_WINDOW_SECONDS:
        row = {'count': 0, 'first_attempt_at': now, 'locked_until': 0}
    row['count'] = int(row.get('count', 0)) + 1
    if row['count'] >= LOGIN_RATE_LIMIT_MAX:
        row['locked_until'] = now + LOGIN_RATE_LIMIT_LOCK_SECONDS
    main.LOGIN_ATTEMPTS[key] = row
    # Opportunistically reclaim memory from expired/overflowing entries.
    _prune_login_attempts(now)


def clear_login_failures(request: Request, username: str):
    main.LOGIN_ATTEMPTS.pop(login_rate_limit_key(request, username), None)

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

def can_admin_family(session: Session, user: User, family_id: int) -> bool:
    """Check if user is admin (global or family-specific) for a family."""
    # Super admin and global admin are admins for all families
    if user.role in ('super_admin', 'admin'):
        return True
    
    # Check family-specific role
    family_role = get_user_family_role(session, user, family_id)
    if family_role == 'admin':
        return True
        
    return False

def can_view_family(session: Session, user: User, family_id: int) -> bool:
    """Check if user can view a specific family."""
    if user.role in ('super_admin', 'admin'):
        return True
    return get_user_family_role(session, user, family_id) is not None

def require_family_edit_permission(family_id: int):
    """Dependency to check family edit permission."""
    def dependency(user: User = Depends(get_current_user), session: Session = Depends(lambda: Session(main.engine))) -> User:
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
    """
    同步配偶关系（双向维护 spouse_ids）。

    并发说明：本函数采用 read-modify-write 模式，其原子性依赖调用方的事务边界。
    在单 worker 部署下是安全的；多 worker / 多进程并发修改同一配偶集合时仍可能丢失
    更新，需要数据库级锁（如 SELECT ... FOR UPDATE 或 SQLite BEGIN IMMEDIATE）才能
    彻底避免，当前实现未提供该保证。
    """
    if not member_id:
        return
    old_ids = {sid for sid in parse_spouse_ids_value(old_spouse_ids) if sid != member_id}
    new_ids = {sid for sid in parse_spouse_ids_value(new_spouse_ids) if sid != member_id}

    # 一次性刷新缓存，确保从数据库读取最新状态
    session.expire_all()

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


def sync_spouse_marriage_details(session: Session, member: Member):
    if not member.id:
        return
    spouse_ids = parse_spouse_ids_value(member.spouse_ids)
    for spouse_id in spouse_ids:
        spouse = session.get(Member, spouse_id)
        if spouse:
            changed = False
            if spouse.marriage_year != member.marriage_year:
                spouse.marriage_year = member.marriage_year
                changed = True
            if spouse.marriage_note != member.marriage_note:
                spouse.marriage_note = member.marriage_note
                changed = True
            if changed:
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
    # 防止 Excel 公式注入：清理可能作为公式执行的前缀
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
        s = "'" + s
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
    nums = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']
    if n < 0 or n > 9999:
        return str(n)
    if n <= 10:
        return ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十'][n]
    if n < 20:
        # 11-19 口语习惯：十一、十二……
        return '十' + nums[n - 10]
    units = ['', '十', '百', '千']
    digits = []
    temp = n
    while temp > 0:
        digits.append(temp % 10)
        temp //= 10
    parts = []
    prev_zero = False
    for i in range(len(digits) - 1, -1, -1):
        d = digits[i]
        if d == 0:
            prev_zero = True
            continue
        if prev_zero and parts:
            parts.append('零')
        prev_zero = False
        parts.append(nums[d] + units[i])
    return ''.join(parts)


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
        p for p in main.BACKUP_DIR.glob('family-*.db')
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
    backup = main.BACKUP_DIR / f'family-{ts}-{safe_reason}.db'
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
    with Session(main.engine) as session:
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
                    # 验证家族名称长度
                    if len(family_name) > 100:
                        raise ValueError(f'家族名称 "{family_name}" 长度超过 100 字符限制')
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

                # 验证成员名称长度
                if len(name) > 100:
                    raise ValueError(f'成员姓名 "{name}" 长度超过 100 字符限制')
                
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

            # 仅对本次导入新增的成员进行关系推导和写入，防止覆盖历史手动修正数据
            for m, _ in member_family_mapping:
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
            
            # 仅对本次新导入成员同步配偶关联
            for m, _ in member_family_mapping:
                sync_member_spouse_links(session, m.id, [], parse_spouse_ids_value(m.spouse_ids))
            session.commit()
            return count
        except Exception:
            session.rollback()
            raise


def ensure_import_template() -> Path:
    path = main.DATA_DIR / 'members-import-template.xlsx'
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
        father = by_id.get(member.father_id) if member.father_id else None
        mother = by_id.get(member.mother_id) if member.mother_id else None
        
        def has_parents(m: Member) -> bool:
            if m.father_id and m.father_id in by_id:
                return True
            if m.mother_id and m.mother_id in by_id:
                return True
            if m.father_name and first_by_name(m.father_name):
                return True
            if m.mother_name and first_by_name(m.mother_name):
                return True
            return False

        if father and mother:
            father_has = has_parents(father)
            mother_has = has_parents(mother)
            if mother_has and not father_has:
                return mother
            if father_has and not mother_has:
                return father
            if getattr(mother, 'is_core_member', True) and not getattr(father, 'is_core_member', True):
                return mother
            return father
        if father:
            return father
        if mother:
            return mother
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

PUBLIC_SETTING_KEYS = {'siteTitle', 'familySurname', 'subtitle', 'coverKicker', 'treeDescription'}
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
        
    # 同步更新主家族的基本属性
    primary_family = session.exec(select(FamilyGroup).where(FamilyGroup.is_primary == True)).first()
    if primary_family:
        primary_family.surname = data.get('familySurname') or primary_family.surname
        primary_family.name = (data.get('familySurname') or '') + '氏宗族'
        primary_family.site_title = data.get('siteTitle') or primary_family.site_title
        primary_family.subtitle = data.get('subtitle') or primary_family.subtitle
        primary_family.cover_kicker = data.get('coverKicker') or primary_family.cover_kicker
        primary_family.description = data.get('treeDescription') or primary_family.description
        session.add(primary_family)

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
        if m.generation is None:
            add('error', 'missing_generation', m, '成员缺少世代信息，可能导致家谱树排序及展示位置混乱')
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
        if min_generation is not None and m.generation is not None and m.generation > min_generation and not (m.father_id or m.mother_id or normalize_name_value(m.father_name) or normalize_name_value(m.mother_name)):
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


