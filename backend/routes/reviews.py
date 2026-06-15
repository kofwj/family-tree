import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
import backend.main as main
from backend.schemas import ReviewRejectPayload

router = APIRouter(tags=["reviews"])

@router.get('/admin/review-requests')
def list_review_requests(_: main.User = Depends(main.require_capability('review.view'))):
    with Session(main.engine) as session:
        rows = session.exec(select(main.ReviewRequest).order_by(main.ReviewRequest.id.desc()).limit(200)).all()
        return [main.review_request_payload(row) for row in rows]

@router.post('/admin/review-requests/{request_id}/approve')
def approve_review_request(request_id: int, reviewer: main.User = Depends(main.require_capability('review.approve'))):
    with Session(main.engine) as session:
        row = session.get(main.ReviewRequest, request_id)
        if not row:
            raise HTTPException(404, '审核请求不存在')
        if row.status != 'pending':
            raise HTTPException(400, '审核请求已处理')
        member = session.get(main.Member, row.member_id)
        if not member:
            raise HTTPException(404, '成员不存在')
        data = json.loads(row.payload_json or '{}')
        
        # 验证新提交的关系是否合法或形成循环
        if 'father_id' in data:
            father_id = data['father_id']
            if father_id:
                father = session.get(main.Member, father_id)
                if not father:
                    raise HTTPException(400, f'所指父亲成员 #{father_id} 不存在')
                main.validate_parent_assignment(session, member.id, father, '父亲')
        if 'mother_id' in data:
            mother_id = data['mother_id']
            if mother_id:
                mother = session.get(main.Member, mother_id)
                if not mother:
                    raise HTTPException(400, f'所指母亲成员 #{mother_id} 不存在')
                main.validate_parent_assignment(session, member.id, mother, '母亲')
        if 'spouse_ids' in data:
            spouse_ids = main.parse_spouse_ids_value(data['spouse_ids'])
            for sid in spouse_ids:
                if sid == member.id:
                    raise HTTPException(400, '配偶不能指向自己')
                spouse = session.get(main.Member, sid)
                if not spouse:
                    raise HTTPException(400, f'所指配偶成员 #{sid} 不存在')

        old_spouse_ids = main.parse_spouse_ids_value(member.spouse_ids)
        before = {key: getattr(member, key, None) for key in data.keys()}
        for k, v in data.items():
            setattr(member, k, v)
        member.updated_at = datetime.now(timezone.utc).isoformat()
        if 'spouse_ids' in data:
            main.sync_member_spouse_links(session, member.id, old_spouse_ids, main.parse_spouse_ids_value(member.spouse_ids))
        if 'primary_family_id' in data:
            new_fam_id = data['primary_family_id']
            old_fam_id = before.get('primary_family_id')
            if old_fam_id != new_fam_id:
                if old_fam_id:
                    old_links = session.exec(select(main.MemberFamilyLink).where(
                        main.MemberFamilyLink.member_id == member.id,
                        main.MemberFamilyLink.family_id == old_fam_id
                    )).all()
                    for l in old_links:
                        session.delete(l)
                if new_fam_id:
                    existing = session.exec(select(main.MemberFamilyLink).where(
                        main.MemberFamilyLink.member_id == member.id,
                        main.MemberFamilyLink.family_id == new_fam_id
                    )).first()
                    if not existing:
                        link = main.MemberFamilyLink(member_id=member.id, family_id=new_fam_id)
                        session.add(link)
        after = {key: getattr(member, key, None) for key in data.keys()}
        changed = {key: {'before': before.get(key), 'after': after.get(key)} for key in data.keys() if before.get(key) != after.get(key)}
        row.status = 'approved'
        row.reviewer_user_id = reviewer.id
        row.reviewer_username = reviewer.username
        row.updated_at = datetime.now(timezone.utc).isoformat()
        main.sync_spouse_marriage_details(session, member)
        session.add(member)
        session.add(row)
        main.write_audit_log(session, reviewer, 'review.approve', target_type='member', target_id=member.id, target_label=member.name, detail={'reviewRequestId': row.id, **main.classify_member_change_detail(changed)})
        session.commit()
        session.refresh(row)
        return main.review_request_payload(row)

@router.post('/admin/review-requests/{request_id}/reject')
def reject_review_request(request_id: int, payload: ReviewRejectPayload, reviewer: main.User = Depends(main.require_capability('review.approve'))):
    with Session(main.engine) as session:
        row = session.get(main.ReviewRequest, request_id)
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
        main.write_audit_log(session, reviewer, 'review.reject', target_type='member', target_id=row.member_id, target_label=row.target_label, detail={'reviewRequestId': row.id, 'note': row.review_note})
        session.commit()
        session.refresh(row)
        return main.review_request_payload(row)
