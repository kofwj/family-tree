from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
import backend.main as main

router = APIRouter(tags=["families"])

@router.get('/families')
def get_families(user: main.User = Depends(main.require_capability('family.view'))):
    with Session(main.engine) as session:
        families = session.exec(select(main.FamilyGroup).where(main.FamilyGroup.is_active == True)).all()
        result = []
        for f in families:
            member_count = len(session.exec(select(main.Member).where(main.Member.primary_family_id == f.id)).all())
            result.append({
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
                'memberCount': member_count,
            })
        return result

@router.get('/families/{family_id}')
def get_family(family_id: int, user: main.User = Depends(main.require_capability('family.view'))):
    with Session(main.engine) as session:
        family = session.get(main.FamilyGroup, family_id)
        if not family:
            raise HTTPException(status_code=404, detail='家族不存在')
        
        # Count members in this family
        member_count = len(session.exec(select(main.Member).where(main.Member.primary_family_id == family_id)).all())
        
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

@router.put('/families/{family_id}')
def update_family(family_id: int, payload: Dict[str, Any], user: main.User = Depends(main.get_current_user)):
    with Session(main.engine) as session:
        # Check family-level edit permission
        if not main.can_edit_family(session, user, family_id):
            raise HTTPException(status_code=403, detail='当前账号无权编辑该家族')
        
        family = session.get(main.FamilyGroup, family_id)
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
        
        main.write_audit_log(session, user, 'family.edit', target_type='family', target_id=family.id, target_label=family.name, detail=payload)
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

@router.get('/families/{family_id}/users')
def get_family_users(family_id: int, user: main.User = Depends(main.require_capability('family.view'))):
    """Get all users with roles in this family."""
    with Session(main.engine) as session:
        family = session.get(main.FamilyGroup, family_id)
        if not family:
            raise HTTPException(status_code=404, detail='家族不存在')
        
        roles = session.exec(
            select(main.UserFamilyRole).where(main.UserFamilyRole.family_id == family_id)
        ).all()
        
        result = []
        for role in roles:
            user_obj = session.get(main.User, role.user_id)
            if user_obj:
                result.append({
                    'userId': user_obj.id,
                    'username': user_obj.username,
                    'displayName': user_obj.display_name,
                    'role': role.role,
                    'createdAt': role.created_at,
                })
        
        return result

@router.post('/families/{family_id}/users')
def add_family_user(family_id: int, payload: Dict[str, Any], user: main.User = Depends(main.get_current_user)):
    """Assign a user to this family with a specific role."""
    with Session(main.engine) as session:
        if not main.can_edit_family(session, user, family_id):
            raise HTTPException(status_code=403, detail='当前账号无权管理该家族的用户权限')
        
        family = session.get(main.FamilyGroup, family_id)
        if not family:
            raise HTTPException(status_code=404, detail='家族不存在')
        
        target_user_id = payload.get('userId')
        role = payload.get('role', 'viewer')
        
        if not target_user_id:
            raise HTTPException(status_code=400, detail='缺少 userId 参数')
        
        target_user = session.get(main.User, target_user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail='用户不存在')
        
        # Check if already exists
        existing = session.exec(
            select(main.UserFamilyRole)
            .where(main.UserFamilyRole.user_id == target_user_id)
            .where(main.UserFamilyRole.family_id == family_id)
        ).first()
        
        if existing:
            existing.role = role
            existing.updated_at = datetime.now(timezone.utc).isoformat()
            session.add(existing)
        else:
            new_role = main.UserFamilyRole(
                user_id=target_user_id,
                family_id=family_id,
                role=role,
            )
            session.add(new_role)
        
        main.write_audit_log(session, user, 'family.assign_user', target_type='family', target_id=family.id, target_label=family.name, detail={'targetUserId': target_user_id, 'role': role})
        session.commit()
        
        return {'ok': True}

@router.delete('/families/{family_id}/users/{user_id}')
def remove_family_user(family_id: int, user_id: int, user: main.User = Depends(main.get_current_user)):
    """Remove a user's role from this family."""
    with Session(main.engine) as session:
        if not main.can_edit_family(session, user, family_id):
            raise HTTPException(status_code=403, detail='当前账号无权管理该家族的用户权限')
        
        role = session.exec(
            select(main.UserFamilyRole)
            .where(main.UserFamilyRole.user_id == user_id)
            .where(main.UserFamilyRole.family_id == family_id)
        ).first()
        
        if not role:
            raise HTTPException(status_code=404, detail='该用户在此家族中没有角色')
        
        session.delete(role)
        main.write_audit_log(session, user, 'family.remove_user', target_type='family', target_id=family_id, target_label=str(family_id), detail={'targetUserId': user_id})
        session.commit()
        
        return {'ok': True}

@router.get('/families/{family_id}/tree')
def get_family_tree(family_id: int, user: main.User = Depends(main.require_capability('tree.view'))):
    with Session(main.engine) as session:
        family = session.get(main.FamilyGroup, family_id)
        if not family:
            raise HTTPException(status_code=404, detail='家族不存在')
        
        visibility = main.build_member_visibility(session, user)
        default_visible_fields = main.resolve_visible_member_fields(session, user)
        
        # Filter members by primary_family_id or family link
        linked_member_ids = session.exec(
            select(main.MemberFamilyLink.member_id).where(main.MemberFamilyLink.family_id == family_id)
        ).all()
        if linked_member_ids:
            all_members = session.exec(
                select(main.Member).where(
                    (main.Member.primary_family_id == family_id) | (main.Member.id.in_(linked_member_ids))
                )
            ).all()
        else:
            all_members = session.exec(
                select(main.Member).where(main.Member.primary_family_id == family_id)
            ).all()
        
        # Crawl descendants and their spouses recursively
        db_members = session.exec(select(main.Member)).all()
        by_id = {m.id: m for m in db_members if m.id is not None}
        family_member_ids = {m.id for m in all_members if m.id is not None}
        
        def get_spouse_ids(m: main.Member) -> list[int]:
            if not m.spouse_ids:
                return []
            import json
            try:
                return [int(x) for x in json.loads(m.spouse_ids) if x is not None]
            except Exception:
                return []

        added = True
        while added:
            added = False
            # 1. Add descendants
            for m in db_members:
                if m.id is not None and m.id not in family_member_ids:
                    if (m.father_id and m.father_id in family_member_ids) or (m.mother_id and m.mother_id in family_member_ids):
                        family_member_ids.add(m.id)
                        all_members.append(m)
                        added = True
            
            # 2. Add spouses of descendants
            for m in db_members:
                if m.id is not None and m.id in family_member_ids:
                    for sp_id in get_spouse_ids(m):
                        if sp_id in by_id and sp_id not in family_member_ids:
                            family_member_ids.add(sp_id)
                            all_members.append(by_id[sp_id])
                            added = True
        
        if visibility is None:
            visible_ids = {m.id for m in all_members if m.id is not None}
            tree_nodes = main.build_tree(session, allowed_ids=visible_ids, visible_fields=default_visible_fields)
            return {'nodes': tree_nodes}
        
        visible_ids = {m.id for m in all_members if m.id is not None and main.can_view_member_with_visibility(user, m, visibility)}
        visible_fields_by_id = {}
        visibility_scope_by_id = {}
        for member_id in visible_ids:
            scope = main.member_visibility_scope(member_id, visibility)
            visible_fields_by_id[member_id] = main.visible_fields_for_scope(default_visible_fields, scope)
            visibility_scope_by_id[member_id] = scope
        
        tree_nodes = main.build_tree(
            session,
            allowed_ids=visible_ids,
            visible_fields=default_visible_fields,
            visible_fields_by_id=visible_fields_by_id,
            visibility_scope_by_id=visibility_scope_by_id,
        )
        return {'nodes': tree_nodes}

@router.get('/tree')
def tree(user: main.User = Depends(main.require_capability('tree.view'))):
    with Session(main.engine) as session:
        visibility = main.build_member_visibility(session, user)
        default_visible_fields = main.resolve_visible_member_fields(session, user)
        all_members = session.exec(select(main.Member)).all()
        if visibility is None:
            visible_ids = {m.id for m in all_members if m.id is not None}
            allowed_ids = None
            return main.build_tree(session, allowed_ids, visible_fields=default_visible_fields)

        visible_ids = {m.id for m in all_members if m.id is not None and main.can_view_member_with_visibility(user, m, visibility)}
        visible_fields_by_id = {}
        visibility_scope_by_id = {}
        for member_id in visible_ids:
            scope = main.member_visibility_scope(member_id, visibility)
            visible_fields_by_id[member_id] = main.visible_fields_for_scope(default_visible_fields, scope)
            visibility_scope_by_id[member_id] = scope
        return main.build_tree(
            session,
            allowed_ids=visible_ids,
            visible_fields=default_visible_fields,
            visible_fields_by_id=visible_fields_by_id,
            visibility_scope_by_id=visibility_scope_by_id,
        )
