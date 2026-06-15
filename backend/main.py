import os
import sys
import tempfile

# Bootstrapper to resolve 'backend' package import issues when running inside Docker container.
current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
backend_dir = None
while current_dir and current_dir != '/':
    if os.path.exists(os.path.join(current_dir, 'database.py')):
        backend_dir = current_dir
        break
    current_dir = os.path.dirname(current_dir)
if not backend_dir:
    backend_dir = '/app'

if os.path.basename(backend_dir) != 'backend':
    tmp_dir = os.path.join(tempfile.gettempdir(), 'family_tree_backend_path')
    os.makedirs(tmp_dir, exist_ok=True)
    symlink_path = os.path.join(tmp_dir, 'backend')
    if not os.path.exists(symlink_path):
        try:
            os.symlink(backend_dir, symlink_path)
        except Exception:
            pass
    if tmp_dir not in sys.path:
        sys.path.insert(0, tmp_dir)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select, create_engine, SQLModel

# Import configurations first so conftest.py can overwrite them on the main module namespace
from backend.database import (
    DATABASE_URL, RUNNING_IN_CONTAINER, DATA_DIR, BACKUP_DIR, PHOTO_DIR,
    connect_args, engine, get_db, JWT_SECRET, JWT_ALG, PASSWORD_MIN_LENGTH,
    PHOTO_MAX_BYTES, EXCEL_MAX_BYTES, LOGIN_RATE_LIMIT_MAX,
    LOGIN_RATE_LIMIT_WINDOW_SECONDS, LOGIN_RATE_LIMIT_LOCK_SECONDS,
    LOGIN_ATTEMPTS, ADMIN_PASSWORD
)

# Import models & schemas for tests/other files that reference them from main.py
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

# Import all helper functions
from backend.helpers import *

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

@app.get('/health')
def health():
    return {'ok': True, 'time': datetime.now(timezone.utc).isoformat()}

# Register routers
from backend.routes.auth import router as auth_router
from backend.routes.members import router as members_router
from backend.routes.families import router as families_router
from backend.routes.reviews import router as reviews_router
from backend.routes.map import router as map_router
from backend.routes.admin import router as admin_router

app.include_router(auth_router)
app.include_router(members_router)
app.include_router(families_router)
app.include_router(reviews_router)
app.include_router(map_router)
app.include_router(admin_router)
