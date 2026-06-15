import os
import shutil
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Response
from fastapi.responses import FileResponse
from sqlmodel import Session, select
import backend.main as main
from backend.schemas import (
    ManagedUserOut, ManagedUserCreate, ManagedUserUpdate,
    PasswordResetPayload, AuditLogOut, AppSettings, SourceIn
)

router = APIRouter(tags=["admin"])

@router.get('/admin/data-quality')
def data_quality(_: main.User = Depends(main.require_capability('quality.view'))):
    with Session(main.engine) as session:
        return main.build_data_quality_report(session)

@router.get('/admin/roles')
def list_roles(_: main.User = Depends(main.require_capability('user.view'))):
    return [
        {'role': role, 'label': main.ROLE_LABELS.get(role, role), 'capabilities': sorted(caps)}
        for role, caps in main.ROLE_CAPABILITIES.items()
    ]

@router.get('/admin/users', response_model=List[ManagedUserOut])
def list_users(_: main.User = Depends(main.require_capability('user.view'))):
    with Session(main.engine) as session:
        users = session.exec(select(main.User).order_by(main.User.id)).all()
        return [main.managed_user_payload(u) for u in users]

@router.get('/admin/audit-logs', response_model=List[AuditLogOut])
def list_audit_logs(user: main.User = Depends(main.require_capability('audit.view'))):
    with Session(main.engine) as session:
        rows = session.exec(select(main.AuditLog).order_by(main.AuditLog.id.desc()).limit(200)).all()
        return [main.audit_log_payload(row) for row in rows]

@router.post('/admin/users', response_model=ManagedUserOut)
def create_user(payload: ManagedUserCreate, actor: main.User = Depends(main.require_capability('user.create'))):
    username = (payload.username or '').strip()
    display_name = (payload.displayName or '').strip() or username
    password = payload.password or ''
    main.validate_new_password(password)
    role = main.validate_role(payload.role) or 'viewer'
    if not username:
        raise HTTPException(status_code=400, detail='用户名不能为空')
    with Session(main.engine) as session:
        exists = session.exec(select(main.User).where(main.User.username == username)).first()
        if exists:
            raise HTTPException(status_code=409, detail='用户名已存在')
        member_id = main.resolve_user_member_id(session, payload.memberId)
        user = main.User(
            username=username,
            display_name=display_name,
            role=role,
            is_active=bool(payload.isActive),
            member_id=member_id,
            email=(payload.email or '').strip() or None,
            phone=(payload.phone or '').strip() or None,
            password_hash=main.hash_password(password),
        )
        session.add(user)
        main.write_audit_log(session, actor, 'user.create', target_type='user', target_id=username, target_label=display_name or username, detail={'role': role, 'memberId': member_id, 'isActive': bool(payload.isActive)})
        session.commit()
        session.refresh(user)
        return main.managed_user_payload(user)

@router.put('/admin/users/{user_id}', response_model=ManagedUserOut)
def update_user(user_id: int, payload: ManagedUserUpdate, current: main.User = Depends(main.require_capability('user.edit_role'))):
    with Session(main.engine) as session:
        user = session.get(main.User, user_id)
        if not user:
            raise HTTPException(404, '用户不存在')
        before = main.managed_user_payload(user)
        if user.username == 'admin' and payload.role and payload.role != 'super_admin':
            raise HTTPException(status_code=400, detail='内置 admin 必须保留超级管理员角色')
        if current.id == user.id and payload.isActive is False:
            raise HTTPException(status_code=400, detail='不能停用当前登录账号')
        if payload.role is not None:
            user.role = main.validate_role(payload.role)
        if payload.displayName is not None:
            user.display_name = payload.displayName.strip() or user.username
        if 'memberId' in payload.model_fields_set:
            user.member_id = main.resolve_user_member_id(session, payload.memberId)
        if payload.email is not None:
            user.email = payload.email.strip() or None
        if payload.phone is not None:
            user.phone = payload.phone.strip() or None
        if payload.isActive is not None:
            user.is_active = bool(payload.isActive)
        user.updated_at = datetime.now(timezone.utc).isoformat()
        after = main.managed_user_payload(user)
        changed = {
            key: {'before': before.get(key), 'after': after.get(key)}
            for key in ['displayName', 'role', 'memberId', 'email', 'phone', 'isActive']
            if before.get(key) != after.get(key)
        }
        session.add(user)
        main.write_audit_log(session, current, 'user.update', target_type='user', target_id=user.id, target_label=user.username, detail=changed)
        session.commit()
        session.refresh(user)
        return main.managed_user_payload(user)

@router.post('/admin/users/{user_id}/disable', response_model=ManagedUserOut)
def disable_user(user_id: int, current: main.User = Depends(main.require_capability('user.disable'))):
    with Session(main.engine) as session:
        user = session.get(main.User, user_id)
        if not user:
            raise HTTPException(404, '用户不存在')
        if current.id == user.id:
            raise HTTPException(status_code=400, detail='不能停用当前登录账号')
        user.is_active = False
        user.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(user)
        main.write_audit_log(session, current, 'user.disable', target_type='user', target_id=user.id, target_label=user.username)
        session.commit()
        session.refresh(user)
        return main.managed_user_payload(user)

@router.post('/admin/users/{user_id}/enable', response_model=ManagedUserOut)
def enable_user(user_id: int, user: main.User = Depends(main.require_capability('user.disable'))):
    with Session(main.engine) as session:
        target = session.get(main.User, user_id)
        if not target:
            raise HTTPException(404, '用户不存在')
        target.is_active = True
        target.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(target)
        main.write_audit_log(session, user, 'user.enable', target_type='user', target_id=target.id, target_label=target.username)
        session.commit()
        session.refresh(target)
        return main.managed_user_payload(target)

@router.post('/admin/users/{user_id}/reset-password')
def reset_user_password(user_id: int, payload: PasswordResetPayload, actor: main.User = Depends(main.require_capability('user.reset_password'))):
    main.validate_new_password(payload.password)
    with Session(main.engine) as session:
        user = session.get(main.User, user_id)
        if not user:
            raise HTTPException(404, '用户不存在')
        user.password_hash = main.hash_password(payload.password)
        user.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(user)
        main.write_audit_log(session, actor, 'user.reset_password', target_type='user', target_id=user.id, target_label=user.username)
        session.commit()
        return {'ok': True}

@router.put('/settings')
def update_settings(payload: AppSettings, actor: main.User = Depends(main.require_capability('settings.edit_basic'))):
    main.backup_db('before-settings-update')
    with Session(main.engine) as session:
        before = main.get_settings_dict(session)
        result = main.save_settings_dict(session, payload)
        changed = {
            key: {'before': before.get(key), 'after': result.get(key)}
            for key in result.keys()
            if before.get(key) != result.get(key)
        }
        main.write_audit_log(session, actor, 'settings.update', target_type='settings', target_id='app', target_label='系统设置', detail=changed)
        session.commit()
        return result

@router.get('/public-settings')
def get_public_settings():
    with Session(main.engine) as session:
        settings = main.get_settings_dict(session)
        return {key: settings.get(key, main.DEFAULT_SETTINGS.get(key)) for key in main.PUBLIC_SETTING_KEYS}

@router.get('/settings')
def get_settings(_: main.User = Depends(main.require_capability('settings.view'))):
    with Session(main.engine) as session:
        return main.get_settings_dict(session)

@router.get('/sources')
def list_sources(_: main.User = Depends(main.require_capability('source.view'))):
    with Session(main.engine) as session:
        rows = session.exec(select(main.SourceRecord).order_by(main.SourceRecord.id.desc())).all()
        return [main.source_payload(row) for row in rows]

@router.post('/sources')
def create_source(payload: SourceIn, user: main.User = Depends(main.require_capability('source.manage'))):
    title = (payload.title or '').strip()
    if not title:
        raise HTTPException(400, '来源标题不能为空')
    now = datetime.now(timezone.utc).isoformat()
    with Session(main.engine) as session:
        row = main.SourceRecord(
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
        main.write_audit_log(session, user, 'source.create', target_type='source', target_id=row.id, target_label=row.title)
        session.commit()
        return main.source_payload(row)

@router.put('/sources/{source_id}')
def update_source(source_id: int, payload: SourceIn, user: main.User = Depends(main.require_capability('source.manage'))):
    with Session(main.engine) as session:
        row = session.get(main.SourceRecord, source_id)
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
        main.write_audit_log(session, user, 'source.update', target_type='source', target_id=row.id, target_label=row.title)
        session.commit()
        session.refresh(row)
        return main.source_payload(row)

@router.delete('/sources/{source_id}')
def delete_source(source_id: int, user: main.User = Depends(main.require_capability('source.manage'))):
    with Session(main.engine) as session:
        row = session.get(main.SourceRecord, source_id)
        if not row:
            raise HTTPException(404, '来源不存在')
        linked = session.exec(select(main.Citation).where(main.Citation.source_id == source_id)).all()
        if linked:
            raise HTTPException(400, '该来源已有引用，不能直接删除')
        title = row.title
        session.delete(row)
        main.write_audit_log(session, user, 'source.delete', target_type='source', target_id=source_id, target_label=title)
        session.commit()
        return {'ok': True}

@router.get('/export/gedcom')
def export_gedcom(_: main.User = Depends(main.require_capability('export.gedcom'))):
    with Session(main.engine) as session:
        content = main.build_gedcom(session)
    filename = f"family-tree-{main.local_timestamp_for_filename()}.ged"
    return Response(
        content=content,
        media_type='text/plain; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )

@router.post('/admin/import-default')
def import_default_disabled(_: main.User = Depends(main.require_capability('member.import'))):
    raise HTTPException(410, '已取消直接导入内置数据，请先下载样表，填写后上传 Excel 导入')

@router.post('/admin/backup')
def make_backup(user: main.User = Depends(main.require_capability('backup.create'))):
    result = main.backup_db('manual')
    with Session(main.engine) as audit_session:
        main.write_audit_log(audit_session, user, 'backup.create', target_type='backup', target_id=result.get('path'), target_label=result.get('path'))
        audit_session.commit()
    return result

@router.get('/admin/backups')
def backups(_: main.User = Depends(main.require_capability('backup.view'))):
    main.prune_auto_backups()
    items = sorted(main.BACKUP_DIR.glob('family-*.db'), key=main.backup_sort_key, reverse=True)
    result = []
    for p in items:
        stat = p.stat()
        meta = main.classify_backup_file(p)
        result.append({
            'file': p.name,
            'path': str(p),
            'size': stat.st_size,
            'mtime': main.local_iso_from_timestamp(stat.st_mtime),
            'createdAt': main.backup_created_at(p),
            'timezone': str(main.LOCAL_TIMEZONE),
            'downloadUrl': f"/api/admin/backups/{quote(p.name)}/download",
            'canDelete': True,
            'deleteHint': '可手动删除；自动保留策略只清理普通自动备份' if meta.get('retentionProtected') else '可手动删除；超过最近30个普通自动备份时会自动清理',
            **meta,
        })
    return result

@router.get('/admin/backups/{filename}/download')
def download_backup(filename: str, _: main.User = Depends(main.require_capability('backup.download'))):
    target = (main.BACKUP_DIR / filename).resolve()
    if main.BACKUP_DIR.resolve() not in target.parents or not target.exists():
        raise HTTPException(404, '备份不存在')
    return FileResponse(path=target, filename=target.name, media_type='application/octet-stream')

@router.delete('/admin/backups/{filename}')
def delete_backup(filename: str, user: main.User = Depends(main.require_capability('backup.delete'))):
    target = (main.BACKUP_DIR / filename).resolve()
    if main.BACKUP_DIR.resolve() not in target.parents or not target.exists():
        raise HTTPException(404, '备份不存在')
    target.unlink()
    with Session(main.engine) as audit_session:
        main.write_audit_log(audit_session, user, 'backup.delete', target_type='backup', target_id=filename, target_label=filename)
        audit_session.commit()
    return {'ok': True, 'deleted': filename}

@router.post('/admin/backups/upload')
async def upload_backup(file: UploadFile, user: main.User = Depends(main.require_capability('backup.restore'))):
    if not file.filename or not file.filename.endswith('.db'):
        raise HTTPException(400, '仅支持 .db 格式的 SQLite 备份文件')
    
    safe_filename = f'uploaded-{main.local_timestamp_for_filename()}-{file.filename}'
    target_path = (main.BACKUP_DIR / safe_filename).resolve()
    
    if main.BACKUP_DIR.resolve() not in target_path.parents:
        raise HTTPException(400, '非法的文件路径')
    
    try:
        content = await file.read()
        with open(target_path, 'wb') as f:
            f.write(content)
        
        main.validate_sqlite_backup_file(target_path)
        
        with Session(main.engine) as audit_session:
            main.write_audit_log(
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
        target_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        target_path.unlink(missing_ok=True)
        raise HTTPException(500, f'上传备份失败: {str(exc)}') from exc

@router.post('/admin/restore/{filename}')
def restore(filename: str, user: main.User = Depends(main.require_capability('backup.restore'))):
    target = (main.BACKUP_DIR / filename).resolve()
    if main.BACKUP_DIR.resolve() not in target.parents or not target.exists():
        raise HTTPException(404, '备份不存在')
    main.validate_sqlite_backup_file(target)
    snapshot = main.backup_db('before-restore')
    db_path = main.sqlite_path()
    staging = main.DATA_DIR / f'restore-{main.local_timestamp_for_filename()}-{uuid.uuid4().hex[:12]}.db'
    try:
        shutil.copy2(target, staging)
        main.validate_sqlite_backup_file(staging)
        main.engine.dispose()
        os.replace(staging, db_path)
        main.init_db()
    except Exception as exc:
        main.engine.dispose()
        try:
            safety_path = Path(snapshot.get('path', ''))
            if safety_path.exists():
                os.replace(safety_path, db_path)
                main.init_db()
        except Exception:
            pass
        try:
            staging.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=500, detail='恢复备份失败，已尝试回滚到恢复前保护备份') from exc
    with Session(main.engine) as audit_session:
        main.write_audit_log(audit_session, user, 'backup.restore', target_type='backup', target_id=filename, target_label=filename, detail={'safetyBackup': snapshot.get('file')})
        audit_session.commit()
    return {'ok': True, 'restored': filename, 'safetyBackup': snapshot}
