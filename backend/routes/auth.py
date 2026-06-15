from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
import backend.main as main
from backend.schemas import Token, CurrentUserOut

router = APIRouter(tags=["auth"])

@router.post('/auth/login', response_model=Token)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
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
        return Token(access_token=main.create_token(user))

@router.get('/me', response_model=CurrentUserOut)
def me(user: main.User = Depends(main.get_current_user)):
    return main.current_user_payload(user)
