from fastapi import APIRouter, Depends, Request, Response, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
import backend.main as main
from backend.schemas import Token, CurrentUserOut

router = APIRouter(tags=["auth"])

from fastapi import Form

@router.post('/auth/login', response_model=Token)
def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    remember_me: bool = Form(False)
):
    main.check_login_rate_limit(request, form.username)
    with Session(main.engine) as session:
        user = session.exec(select(main.User).where(main.User.username == form.username)).first()
        if not user or not user.is_active or not main.verify_password(form.password, user.password_hash):
            main.record_login_failure(request, form.username)
            main.write_audit_log(session, None, 'auth.login_failed', target_type='user', target_id=None, target_label=form.username, detail={'ip': request.client.host if request.client else 'unknown'})
            session.commit()
            raise main.HTTPException(status_code=401, detail='用户名或密码错误')
        main.clear_login_failures(request, form.username)
        user.last_login_at = main.datetime.now(main.timezone.utc).isoformat()
        main.write_audit_log(session, user, 'auth.login', target_type='user', target_id=user.id, target_label=user.username)
        session.add(user)
        session.commit()

        hours = 24 * 30 if remember_me else 24
        token_str = main.create_token_with_expiry(user, hours=hours)
        max_age = int(hours * 3600)
        response.set_cookie(
            key="access_token",
            value=token_str,
            httponly=True,
            secure=main.SECURE_COOKIE,
            samesite="lax",
            path="/",
            max_age=max_age
        )
        return Token(access_token=token_str)

@router.post('/auth/logout')
def logout(response: Response):
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=main.SECURE_COOKIE,
        httponly=True,
        samesite="lax"
    )
    return {'ok': True}

@router.get('/me', response_model=CurrentUserOut)
def me(user: main.User = Depends(main.get_current_user)):
    return main.current_user_payload(user)

import secrets

# 简单的 state 存储（生产建议用 Redis）
_WECHAT_STATES = {}


@router.get("/auth/wechat/qr-url")
def wechat_qr_url():
    """返回微信扫码登录 URL"""
    import backend.main as main
    state = secrets.token_urlsafe(16)
    _WECHAT_STATES[state] = True
    try:
        qr_url = main.build_wechat_qr_url(state)
        return {"qr_url": qr_url, "state": state}
    except Exception as e:
        raise main.HTTPException(status_code=500, detail=str(e))


@router.get("/auth/wechat/callback")
def wechat_callback(request: Request, response: Response, code: str = None, state: str = None):
    """微信回调：code 换 token → 查找/创建用户 → 设置 cookie → 跳转"""
    if not code or not state or state not in _WECHAT_STATES:
        return RedirectResponse(url="/login?error=wechat_invalid_state")

    _WECHAT_STATES.pop(state, None)

    try:
        token_data = main.exchange_wechat_web_code(code)
        openid = token_data.get("openid")
        access_token = token_data.get("access_token")
        unionid = token_data.get("unionid")

        nickname = None
        avatar = None
        if access_token and openid:
            info = main.get_wechat_userinfo(access_token, openid)
            nickname = info.get("nickname")
            avatar = info.get("headimgurl")

        with Session(main.engine) as session:
            user = main.find_or_create_wechat_user(
                session,
                {"openid": openid, "unionid": unionid},
                nickname=nickname,
                avatar=avatar
            )
            user.last_login_at = main.datetime.now(main.timezone.utc).isoformat()
            session.add(user)
            session.commit()

            token_str = main.create_token(user)
            response.set_cookie(
                key="access_token",
                value=token_str,
                httponly=True,
                secure=main.SECURE_COOKIE,
                samesite="lax",
                path="/"
            )

            # 登录成功后跳转
            # 如果没有绑定 member_id，前端可根据 /me 的 memberId 判断是否需要引导绑定
            redirect_to = "/workspace"
            if not user.member_id:
                redirect_to = "/workspace?needBind=1"
            return RedirectResponse(url=redirect_to)

    except Exception as e:
        main.write_audit_log(None, None, "auth.wechat_failed", target_type="user", detail={"error": str(e)})
        return RedirectResponse(url=f"/login?error=wechat_failed&msg={str(e)[:100]}")

@router.post("/auth/bind-member")
def bind_member(payload: dict, user: main.User = Depends(main.get_current_user)):
    """已登录用户自助绑定家族成员身份"""
    member_id = payload.get("memberId")
    if not member_id:
        raise main.HTTPException(status_code=400, detail="memberId 必填")

    with Session(main.engine) as session:
        member = session.exec(select(main.Member).where(main.Member.id == member_id)).first()
        if not member:
            raise main.HTTPException(status_code=404, detail="成员不存在")

        # 简单策略：如果该 member 已被别人绑定，允许覆盖或拒绝（这里先允许自助绑定，生产可加强校验）
        user.member_id = member_id
        session.add(user)
        session.commit()

        main.write_audit_log(session, user, "user.bind_member", target_type="user", target_id=str(user.id), detail={"memberId": member_id})

        # 返回最新 payload
        return main.current_user_payload(user)


@router.post("/auth/generate-password")
def generate_password(payload: dict = None, user: main.User = Depends(main.get_current_user)):
    """管理员或有权限的人生成一个符合规则的密码（用于创建用户时推荐给老人用）"""
    hint = None
    if payload:
        hint = payload.get("hint") or payload.get("base")
    try:
        pwd = main.generate_compliant_password(hint)
    except Exception:
        pwd = main.generate_compliant_password()
    return {"password": pwd, "hint": "已自动满足强密码规则（字母+数字+特殊字符）"}


# 简单的忘记密码 token 存储（内存，适合小规模家族系统）
_RESET_TOKENS: dict = {}   # token -> {user_id, expires_at, username}

@router.post("/auth/forgot-password")
def forgot_password(payload: dict):
    """忘记密码：输入用户名或联系方式（email/phone），生成重置码"""
    username = (payload.get("username") or "").strip()
    contact = (payload.get("contact") or payload.get("email") or payload.get("phone") or "").strip().lower()

    with Session(main.engine) as session:
        user = None
        if username:
            user = session.exec(select(main.User).where(main.User.username == username)).first()
        if not user and contact:
            user = session.exec(
                select(main.User).where(
                    (main.User.email == contact) | (main.User.phone == contact)
                )
            ).first()

        if not user or not user.is_active:
            # 为了安全，不透露用户是否存在
            return {"ok": True, "message": "如果账号存在且绑定了联系方式，将生成重置信息"}

        import secrets
        from datetime import timedelta
        token = secrets.token_urlsafe(8)[:10]   # 短码，方便口头告诉
        expires = (main.datetime.now(main.timezone.utc) + timedelta(hours=6)).isoformat()

        _RESET_TOKENS[token] = {
            "user_id": user.id,
            "username": user.username,
            "expires_at": expires
        }

        # 实际生产应该发邮件/短信。这里直接返回 token 给前端，管理员可转发给用户
        return {
            "ok": True,
            "message": "重置码已生成（有效期6小时），请联系管理员获取重置码",
            "reset_token": token   # 小规模家族可直接展示或由管理员读取
        }

@router.post("/auth/reset-password")
def reset_password(payload: dict):
    """使用重置码 + 新密码重置"""
    token = (payload.get("token") or "").strip()
    new_password = payload.get("new_password") or payload.get("password") or ""

    if not token or token not in _RESET_TOKENS:
        raise main.HTTPException(status_code=400, detail="重置码无效或已过期")

    info = _RESET_TOKENS[token]
    if main.datetime.fromisoformat(info["expires_at"]) < main.datetime.now(main.timezone.utc):
        _RESET_TOKENS.pop(token, None)
        raise main.HTTPException(status_code=400, detail="重置码已过期")

    main.validate_new_password(new_password)

    with Session(main.engine) as session:
        user = session.get(main.User, info["user_id"])
        if not user:
            raise main.HTTPException(status_code=404, detail="用户不存在")

        user.password_hash = main.hash_password(new_password)
        user.updated_at = main.datetime.now(main.timezone.utc).isoformat()
        session.add(user)
        main.write_audit_log(session, None, "auth.password_reset", target_type="user", target_id=str(user.id), target_label=user.username)
        session.commit()

    _RESET_TOKENS.pop(token, None)
    return {"ok": True, "message": "密码重置成功，请使用新密码登录"}



# ==================== 家族邀请码注册（管理员生成邀请码，家人用码自助注册） ====================

_INVITE_CODES: dict = {}   # code -> {member_id, expires, max_uses, used_count, created_by}

@router.post("/admin/invites")
def create_invite(payload: dict, actor: main.User = Depends(main.require_capability("user.create"))):
    import secrets
    from datetime import timedelta
    code = (payload.get("code") or secrets.token_urlsafe(6)[:8]).upper()
    member_id = payload.get("memberId")
    days = int(payload.get("days", 30))
    max_uses = int(payload.get("maxUses", 1))

    expires = (main.datetime.now(main.timezone.utc) + timedelta(days=days)).isoformat()

    _INVITE_CODES[code] = {
        "code": code,
        "member_id": member_id,
        "expires_at": expires,
        "max_uses": max_uses,
        "used_count": 0,
        "created_by": actor.username,
    }
    return {"code": code, "expires_at": expires, "max_uses": max_uses}

@router.get("/admin/invites")
def list_invites(_: main.User = Depends(main.require_capability("user.view"))):
    now = main.datetime.now(main.timezone.utc)
    result = []
    for c, info in list(_INVITE_CODES.items()):
        if main.datetime.fromisoformat(info["expires_at"]) < now or info["used_count"] >= info["max_uses"]:
            continue
        result.append(info)
    return result

@router.post("/auth/register")
def register_with_invite(payload: dict):
    """用邀请码自助注册"""
    code = (payload.get("inviteCode") or "").upper().strip()
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    display_name = payload.get("displayName") or username

    if not code or code not in _INVITE_CODES:
        raise main.HTTPException(status_code=400, detail="邀请码无效")

    info = _INVITE_CODES[code]
    if main.datetime.fromisoformat(info["expires_at"]) < main.datetime.now(main.timezone.utc):
        raise main.HTTPException(status_code=400, detail="邀请码已过期")
    if info["used_count"] >= info["max_uses"]:
        raise main.HTTPException(status_code=400, detail="邀请码已用完")

    main.validate_new_password(password)
    if not username:
        raise main.HTTPException(status_code=400, detail="用户名不能为空")

    with Session(main.engine) as session:
        exists = session.exec(select(main.User).where(main.User.username == username)).first()
        if exists:
            raise main.HTTPException(status_code=409, detail="用户名已存在")

        user = main.User(
            username=username,
            password_hash=main.hash_password(password),
            role="viewer",
            is_active=True,
            display_name=display_name,
            member_id=info.get("member_id"),
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        info["used_count"] += 1

        main.write_audit_log(session, None, "auth.register_with_invite", target_type="user", target_id=str(user.id), target_label=username, detail={"invite": code})
        session.commit()

    return {"ok": True, "message": "注册成功，请登录", "username": username}
