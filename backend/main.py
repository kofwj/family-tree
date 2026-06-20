import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select, create_engine, SQLModel

# Import configurations first so conftest.py can overwrite them on the main module namespace
from backend.database import (
    DATABASE_URL, RUNNING_IN_CONTAINER, DATA_DIR, BACKUP_DIR, PHOTO_DIR,
    connect_args, engine, get_db, JWT_SECRET, JWT_ALG, PASSWORD_MIN_LENGTH,
    PHOTO_MAX_BYTES, EXCEL_MAX_BYTES, BACKUP_MAX_BYTES, LOGIN_RATE_LIMIT_MAX,
    LOGIN_RATE_LIMIT_WINDOW_SECONDS, LOGIN_RATE_LIMIT_LOCK_SECONDS,
    LOGIN_ATTEMPTS, ADMIN_PASSWORD, SECURE_COOKIE
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

if RUNNING_IN_CONTAINER:
    # Strict production origins
    allow_origins = [os.getenv('CORS_ORIGIN', 'http://localhost:8088')]
else:
    # Dev origins
    allow_origins = [os.getenv('CORS_ORIGIN', 'http://localhost:8088'), 'http://localhost:5173', 'http://localhost:8088']

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
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
