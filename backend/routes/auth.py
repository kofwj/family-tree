from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
import backend.main as main
from backend.schemas import Token, CurrentUserOut

router = APIRouter(tags=["auth"])

@router.post('/auth/login', response_model=Token)
def login(request: Request, response: Response, form: OAuth2PasswordRequestForm = Depends()):
    main.check_login_rate_limit(request, form.username)
    with Session(main.engine) as session:
        user = session.exec(select(main.User).where(main.User.username == form.username)).first()
        if not user or not user.is_active or not main.verify_password(form.password, user.password_hash):
            main.record_login_failure(request, form.username)
            raise main.HTTPException(status_code=401, detail='用户名或密码错误')
        main.clear_login_failures(request, form.username)
        user.last_login_at = main.datetime.now(main.timezone.utc).isoformat()
        main.write_audit_log(session, user, 'auth.login', target_type='user', target_id=user.id, target_label=user.username)
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
