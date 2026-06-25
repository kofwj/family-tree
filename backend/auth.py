import os
import base64
import hashlib
import hmac
from typing import Optional, Dict, Any, Set
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlmodel import Session, select

from backend.database import (
    engine, JWT_SECRET, JWT_ALG, PASSWORD_MIN_LENGTH,
    is_strong_password_value, ADMIN_PASSWORD
)
from backend.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/login', auto_error=False)

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

def get_user_capabilities(user: User) -> Set[str]:
    return set(ROLE_CAPABILITIES.get(user.role, ROLE_CAPABILITIES['viewer']))

def get_current_user(request: Request, token: Optional[str] = Depends(oauth2_scheme)) -> User:
    import backend.main as main
    cookie_token = request.cookies.get('access_token')
    token_to_use = token or cookie_token
    if not token_to_use:
        raise HTTPException(status_code=401, detail='登录状态无效')
    try:
        payload = jwt.decode(token_to_use, main.JWT_SECRET, algorithms=[JWT_ALG])
        username = payload.get('sub')
        if not username:
            raise HTTPException(status_code=401, detail='登录状态无效')
    except JWTError:
        raise HTTPException(status_code=401, detail='登录状态无效')
    with Session(main.engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail='账号不存在或已停用')
        session.expunge(user)
        return user

def require_capability(capability: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if capability not in get_user_capabilities(user):
            raise HTTPException(status_code=403, detail='当前账号无权执行此操作')
        return user
    return dependency
