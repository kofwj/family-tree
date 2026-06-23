import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlmodel import Session, select
import backend.main as main
from backend.schemas import MemberCreate, MemberUpdate, CitationIn

router = APIRouter(tags=["members"])

@router.get('/members')
def list_members(user: main.User = Depends(main.require_capability('member.view'))):
    with Session(main.engine) as session:
        visibility = main.build_member_visibility(session, user)
        scope_ids = None if visibility is None else (visibility.get(main.VISIBILITY_SCOPE_FULL, set()) | visibility.get(main.VISIBILITY_SCOPE_BASIC, set()))
        default_visible_fields = main.resolve_visible_member_fields(session, user)
        members = session.exec(select(main.Member).order_by(main.Member.generation, main.Member.rank_no, main.Member.id)).all()
        if scope_ids is not None:
            members = [m for m in members if m.id in scope_ids]
        members = [m for m in members if main.can_view_member_with_visibility(user, m, visibility)]
        by_id = {m.id: m for m in members if m.id is not None}
        result = []
        for m in members:
            scope = main.member_visibility_scope(m.id, visibility)
            payload = main.member_to_dict(m, visible_fields=main.visible_fields_for_scope(default_visible_fields, scope), by_id=by_id, all_members=members)
            result.append(main.attach_visibility_payload(payload, scope))
        return result

@router.get('/members/{member_id}')
def get_member(member_id: int, user: main.User = Depends(main.require_capability('member.view'))):
    with Session(main.engine) as session:
        m = session.get(main.Member, member_id)
        if not m:
            raise HTTPException(404, '成员不存在')
        visibility = main.build_member_visibility(session, user)
        if not main.can_view_member_with_visibility(user, m, visibility):
            raise HTTPException(status_code=403, detail='当前账号无权访问该成员')
        scope = main.member_visibility_scope(m.id, visibility)
        default_visible_fields = main.resolve_visible_member_fields(session, user)
        all_members = session.exec(select(main.Member)).all()
        if visibility is not None:
            visible_ids = visibility.get(main.VISIBILITY_SCOPE_FULL, set()) | visibility.get(main.VISIBILITY_SCOPE_BASIC, set())
            all_members = [x for x in all_members if x.id in visible_ids and main.can_view_member_with_visibility(user, x, visibility)]
        payload = main.member_to_dict(m, visible_fields=main.visible_fields_for_scope(default_visible_fields, scope), by_id={x.id: x for x in all_members if x.id is not None}, all_members=all_members)
        return main.attach_visibility_payload(payload, scope)

@router.post('/members')
def create_member(payload: MemberCreate, user: main.User = Depends(main.require_capability('member.create'))):
    main.backup_db('before-create')
    data = main.filter_member_payload_for_user(user, payload, for_create=True)
    if not data.get('name'):
        raise HTTPException(status_code=403, detail='当前账号不可创建成员或缺少必要字段')
    with Session(main.engine) as session:
        data = main.resolve_relation_payload(session, data)
        scope_ids = main.build_member_full_scope(session, user)
        if scope_ids is not None:
            allowed_parent_ids = {pid for pid in [data.get('father_id'), data.get('mother_id')] if pid}
            allowed_spouse_ids = set(data.get('spouse_ids') or [])
            if allowed_parent_ids:
                if not allowed_parent_ids.intersection(scope_ids):
                    raise HTTPException(status_code=403, detail='当前账号仅可在自己归属分支下新增成员')
            elif allowed_spouse_ids:
                if not allowed_spouse_ids.intersection(scope_ids):
                    raise HTTPException(status_code=403, detail='当前账号仅可在自己归属分支下新增成员')
            else:
                raise HTTPException(status_code=403, detail='当前账号新增成员时必须挂接到自己归属分支内的父亲或母亲')
        data['spouse_ids'] = main.encode_spouse_ids_value(data.get('spouse_ids') or [])
        
        # Set primary_family_id if not provided
        if 'primary_family_id' not in data or data['primary_family_id'] is None:
            father_id = data.get('father_id')
            mother_id = data.get('mother_id')
            spouse_ids = main.parse_spouse_ids_value(data.get('spouse_ids'))
            
            inherited_family_id = None
            if father_id:
                father = session.get(main.Member, father_id)
                if father and father.primary_family_id:
                    inherited_family_id = father.primary_family_id
            if not inherited_family_id and mother_id:
                mother = session.get(main.Member, mother_id)
                if mother and mother.primary_family_id:
                    inherited_family_id = mother.primary_family_id
            if not inherited_family_id and spouse_ids:
                first_spouse = session.get(main.Member, spouse_ids[0])
                if first_spouse and first_spouse.primary_family_id:
                    inherited_family_id = first_spouse.primary_family_id
                    
            if inherited_family_id:
                data['primary_family_id'] = inherited_family_id
            else:
                primary_family = session.exec(select(main.FamilyGroup).where(main.FamilyGroup.is_primary == True)).first()
                if primary_family:
                    data['primary_family_id'] = primary_family.id
        
        # 自动推导世代信息
        if 'generation' not in data or data['generation'] is None:
            father_id = data.get('father_id')
            mother_id = data.get('mother_id')
            spouse_ids = main.parse_spouse_ids_value(data.get('spouse_ids'))
            
            inherited_gen = None
            if father_id:
                father = session.get(main.Member, father_id)
                if father and father.generation is not None:
                    inherited_gen = father.generation + 1
            if not inherited_gen and mother_id:
                mother = session.get(main.Member, mother_id)
                if mother and mother.generation is not None:
                    inherited_gen = mother.generation + 1
            if not inherited_gen and spouse_ids:
                first_spouse = session.get(main.Member, spouse_ids[0])
                if first_spouse and first_spouse.generation is not None:
                    inherited_gen = first_spouse.generation
            
            if inherited_gen is not None:
                data['generation'] = inherited_gen
            else:
                data['generation'] = 1
        
        family_id = data.get('primary_family_id')
        if family_id and not main.can_edit_family(session, user, family_id):
            raise HTTPException(status_code=403, detail='当前账号无权在此家族中创建成员')
        
        m = main.Member(**data)
        session.add(m)
        session.commit()
        session.refresh(m)
        
        # 建立多家族关联记录，保持数据同步
        if m.id and m.primary_family_id:
            link = main.MemberFamilyLink(member_id=m.id, family_id=m.primary_family_id)
            session.add(link)
            
        main.sync_member_spouse_links(session, m.id, [], main.parse_spouse_ids_value(m.spouse_ids))
        main.sync_spouse_marriage_details(session, m)
        main.write_audit_log(session, user, 'member.create', target_type='member', target_id=m.id, target_label=m.name, detail={'fatherName': m.father_name, 'motherName': m.mother_name, 'generation': m.generation})
        session.commit()
        all_members = session.exec(select(main.Member)).all()
        return main.member_to_dict(m, all_members=all_members)

@router.get('/member-photos/{filename}')
def get_member_photo(filename: str, user: main.User = Depends(main.require_capability('member.view'))):
    target = (main.PHOTO_DIR / filename).resolve()
    if main.PHOTO_DIR.resolve() not in target.parents or not target.exists() or not target.is_file():
        raise HTTPException(404, '照片不存在')
    expected_path = f'/api/member-photos/{filename}'
    with Session(main.engine) as session:
        member = session.exec(select(main.Member).where(
            (main.Member.photo_path == expected_path) |
            (main.Member.photo_path == f'/member-photos/{filename}') |
            (main.Member.photo_path == filename) |
            (main.Member.photo_path.like(f'%/{filename}'))
        )).first()
        if not member or not main.can_view_member_with_visibility(user, member, main.build_member_visibility(session, user)):
            raise HTTPException(status_code=403, detail='当前账号无权访问该成员照片')
    media_type = main.detect_image_mime(target.read_bytes()[:512]) or 'application/octet-stream'
    return FileResponse(path=target, media_type=media_type)

@router.post('/members/{member_id}/photo')
def upload_member_photo(member_id: int, file: UploadFile = File(...), user: main.User = Depends(main.require_capability('member.edit_profile'))):
    suffix = Path(file.filename or '').suffix.lower()
    main.validate_photo_upload(file, suffix)
    main.backup_db(f'before-photo-{member_id}')
    with Session(main.engine) as session:
        m = session.get(main.Member, member_id)
        main.require_member_in_full_scope(session, user, m)
        filename = f'member-{member_id}-{main.local_timestamp_for_filename()}-{uuid.uuid4().hex[:12]}{suffix}'
        target = main.PHOTO_DIR / filename
        main.save_limited_upload(file, target, main.PHOTO_MAX_BYTES, label='照片')
        m.photo_path = f'/api/member-photos/{filename}'
        m.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(m)
        main.write_audit_log(session, user, 'member.upload_photo', target_type='member', target_id=m.id, target_label=m.name, detail={'photo': filename})
        session.commit()
        session.refresh(m)
        all_members = session.exec(select(main.Member)).all()
        return main.member_to_dict(m, all_members=all_members)

@router.put('/members/{member_id}')
def update_member(member_id: int, payload: MemberUpdate, user: main.User = Depends(main.require_capability('member.edit_profile'))):
    main.backup_db(f'before-update-{member_id}')
    raw_data = payload.model_dump(exclude_unset=True)
    data = main.filter_member_payload_for_user(user, payload, for_create=False)
    requested_structure = {k: v for k, v in raw_data.items() if k in main.CORE_RELATION_FIELDS}
    with Session(main.engine) as session:
        m = session.get(main.Member, member_id)
        main.require_member_in_full_scope(session, user, m)
        if m.primary_family_id and not main.can_edit_family(session, user, m.primary_family_id):
            raise HTTPException(status_code=403, detail='当前账号无权编辑此成员所属家族的资料')
        if 'primary_family_id' in data:
            new_family_id = data['primary_family_id']
            if new_family_id and new_family_id != m.primary_family_id:
                if not main.can_edit_family(session, user, new_family_id):
                    raise HTTPException(status_code=403, detail='当前账号无权将成员转移到该家族')
        review_request = None
        if requested_structure and 'member.edit_core_relation' not in main.get_user_capabilities(user):
            review_request = main.create_member_review_request_if_changed(session, user, m, requested_structure)
        if not data:
            if review_request:
                session.commit()
                return {'ok': True, 'pendingReview': main.review_request_payload(review_request), 'member': main.member_to_dict(m)}
            raise HTTPException(status_code=403, detail='当前账号无可编辑字段')
        old_spouse_ids = main.parse_spouse_ids_value(m.spouse_ids)
        data = main.resolve_relation_payload(session, data, current_member_id=member_id)
        if 'spouse_ids' in data:
            data['spouse_ids'] = main.encode_spouse_ids_value(data.get('spouse_ids') or [])
        before = {key: getattr(m, key, None) for key in data.keys()}
        for k, v in data.items():
            setattr(m, k, v)
        m.updated_at = datetime.now(timezone.utc).isoformat()
        if 'spouse_ids' in data:
            main.sync_member_spouse_links(session, m.id, old_spouse_ids, main.parse_spouse_ids_value(m.spouse_ids))
        if 'primary_family_id' in data:
            new_fam_id = data['primary_family_id']
            old_fam_id = before.get('primary_family_id')
            if old_fam_id != new_fam_id:
                if old_fam_id:
                    old_links = session.exec(select(main.MemberFamilyLink).where(
                        main.MemberFamilyLink.member_id == m.id,
                        main.MemberFamilyLink.family_id == old_fam_id
                    )).all()
                    for l in old_links:
                        session.delete(l)
                if new_fam_id:
                    existing = session.exec(select(main.MemberFamilyLink).where(
                        main.MemberFamilyLink.member_id == m.id,
                        main.MemberFamilyLink.family_id == new_fam_id
                    )).first()
                    if not existing:
                        link = main.MemberFamilyLink(member_id=m.id, family_id=new_fam_id)
                        session.add(link)
        after = {key: getattr(m, key, None) for key in data.keys()}
        changed = {
            key: {'before': before.get(key), 'after': after.get(key)}
            for key in data.keys()
            if before.get(key) != after.get(key)
        }
        audit_detail = main.classify_member_change_detail(changed)
        if review_request:
            audit_detail['pendingReviewId'] = review_request.id
        session.add(m)
        main.sync_spouse_marriage_details(session, m)
        main.write_audit_log(session, user, 'member.update', target_type='member', target_id=m.id, target_label=m.name, detail=audit_detail)
        session.commit()
        session.refresh(m)
        all_members = session.exec(select(main.Member)).all()
        result = main.member_to_dict(m, all_members=all_members)
        if review_request:
            result['pendingReview'] = main.review_request_payload(review_request)
        return result

@router.delete('/members/{member_id}')
def delete_member(member_id: int, user: main.User = Depends(main.require_capability('member.delete'))):
    main.backup_db(f'before-delete-{member_id}')
    with Session(main.engine) as session:
        m = session.get(main.Member, member_id)
        main.require_member_in_full_scope(session, user, m)
        main.ensure_member_can_be_deleted(session, member_id)
        main.sync_member_spouse_links(session, m.id, main.parse_spouse_ids_value(m.spouse_ids), [])
        
        # 清理多家族关联表中的关联记录，避免脏数据残留
        links = session.exec(select(main.MemberFamilyLink).where(main.MemberFamilyLink.member_id == member_id)).all()
        for link in links:
            session.delete(link)
            
        main.write_audit_log(session, user, 'member.delete', target_type='member', target_id=m.id, target_label=m.name, detail={'generation': m.generation, 'fatherName': m.father_name, 'motherName': m.mother_name})
        session.delete(m)
        session.commit()
        return {'ok': True}

@router.get('/members/{member_id}/citations')
def list_member_citations(member_id: int, user: main.User = Depends(main.require_capability('source.view'))):
    with Session(main.engine) as session:
        member = session.get(main.Member, member_id)
        if not member:
            raise HTTPException(404, '成员不存在')
        visibility = main.build_member_visibility(session, user)
        if not main.can_view_member_with_visibility(user, member, visibility):
            raise HTTPException(status_code=403, detail='当前账号无权访问该成员')
        if main.member_visibility_scope(member.id, visibility) == main.VISIBILITY_SCOPE_BASIC:
            return []
        rows = session.exec(select(main.Citation).where(main.Citation.member_id == member_id).order_by(main.Citation.id.desc())).all()
        sources = {s.id: s for s in session.exec(select(main.SourceRecord)).all() if s.id is not None}
        return [main.citation_payload(row, sources.get(row.source_id)) for row in rows]

@router.post('/members/{member_id}/citations')
def create_member_citation(member_id: int, payload: CitationIn, user: main.User = Depends(main.require_capability('source.manage'))):
    with Session(main.engine) as session:
        member = session.get(main.Member, member_id)
        main.require_member_in_full_scope(session, user, member)
        source = session.get(main.SourceRecord, payload.source_id)
        if not source:
            raise HTTPException(400, '来源不存在')
        row = main.Citation(
            member_id=member_id,
            source_id=payload.source_id,
            field_name=(payload.field_name or '').strip() or None,
            quote_text=(payload.quote_text or '').strip() or None,
            note=(payload.note or '').strip() or None,
        )
        session.add(row)
        main.write_audit_log(session, user, 'source.cite', target_type='member', target_id=member_id, target_label=member.name, detail={'sourceId': source.id, 'fieldName': row.field_name})
        session.commit()
        session.refresh(row)
        return main.citation_payload(row, source)

@router.get('/members/{member_id}/ancestry')
def get_member_ancestry(
    member_id: int,
    mode: str = 'four-line',
    generations: int = 3,
    user: main.User = Depends(main.require_capability('member.view'))
):
    with Session(main.engine) as session:
        member = session.get(main.Member, member_id)
        if not member:
            raise HTTPException(status_code=404, detail='成员不存在')
        
        visibility = main.build_member_visibility(session, user)
        if not main.can_view_member_with_visibility(user, member, visibility):
            raise HTTPException(status_code=403, detail='当前账号无权访问该成员的祖源信息')
            
        all_members = session.exec(select(main.Member)).all()
        by_id = {m.id: m for m in all_members if m.id is not None}
        
        def trace_line(start_id: int, parent_getter, max_gen: int):
            line = []
            current_id = start_id
            for _ in range(max_gen):
                if current_id is None or current_id not in by_id:
                    break
                current = by_id[current_id]
                if not main.can_view_member_with_visibility(user, current, visibility):
                    # Hard truncation: stop tracing this ancestral branch immediately
                    break
                
                scope = main.member_visibility_scope(current.id, visibility)
                default_visible_fields = main.resolve_visible_member_fields(session, user)
                visible_fields = main.visible_fields_for_scope(default_visible_fields, scope)
                
                payload = main.member_to_dict(current, include_relations=False, visible_fields=visible_fields, by_id=by_id, all_members=all_members)
                line.append(main.attach_visibility_payload(payload, scope))
                current_id = parent_getter(current)
            return line
        
        scope = main.member_visibility_scope(member.id, visibility)
        default_visible_fields = main.resolve_visible_member_fields(session, user)
        visible_fields = main.visible_fields_for_scope(default_visible_fields, scope)
        
        member_payload = main.member_to_dict(member, include_relations=False, visible_fields=visible_fields, by_id=by_id, all_members=all_members)
        member_payload = main.attach_visibility_payload(member_payload, scope)
        
        result = {
            'member': member_payload,
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

@router.post('/import/excel')
def upload_excel(file: UploadFile = File(...), user: main.User = Depends(main.require_capability('member.import'))):
    main.backup_db('before-import')
    filename = file.filename or ''
    suffix = Path(filename).suffix.lower()
    if suffix != '.xlsx':
        raise HTTPException(status_code=400, detail='仅支持 .xlsx Excel 文件导入')
    tmp = main.DATA_DIR / f'upload-{main.local_timestamp_for_filename()}-{uuid.uuid4().hex[:12]}.xlsx'
    try:
        main.save_limited_upload(file, tmp, main.EXCEL_MAX_BYTES, label='Excel文件')
        count = main.import_excel(str(tmp), replace=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    with Session(main.engine) as audit_session:
        main.write_audit_log(audit_session, user, 'member.import_excel', target_type='import', target_id=tmp.name, target_label=file.filename or tmp.name, detail={'count': count})
        audit_session.commit()
    return {'ok': True, 'count': count}

@router.get('/import/template')
def download_import_template(_: main.User = Depends(main.require_capability('member.import'))):
    path = main.ensure_import_template()
    return FileResponse(
        path=path,
        filename='家谱成员导入样表.xlsx',
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
