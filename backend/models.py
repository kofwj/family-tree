from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field

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

class SiteSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: Optional[str] = None
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
