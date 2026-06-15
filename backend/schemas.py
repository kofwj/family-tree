from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel

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
    name: Optional[str] = None

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
