import hashlib
import hmac
import os
import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select

from .common import DB, data
from .db import User, LoginSession, Initialization, now

router = APIRouter(prefix='/api')
attempts = defaultdict(deque)


class Credentials(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    username: str = Field(min_length=2, max_length=80, pattern=r'^[\w.@-]+$')
    password: str = Field(min_length=12, max_length=128)
    setup_token: str = ''


def password_hash(password):
    salt = secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ':' + value


def verify(password, stored):
    salt, expected = stored.split(':')
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(actual, expected)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request, db: DB):
    token = request.cookies.get('sales_session', '')
    login = db.get(LoginSession, digest(token)) if token else None
    if login is None or login.expires_at < now():
        raise HTTPException(401, '请登录')
    return db.get(User, login.user_id)


Auth = Annotated[User, Depends(current_user)]


@router.get('/auth/status')
def status(request: Request, db: DB):
    token = request.cookies.get('sales_session', '')
    login = db.get(LoginSession, digest(token)) if token else None
    user = db.get(User, login.user_id) if login and login.expires_at >= now() else None
    return {'initialized': db.scalar(select(User.id).limit(1)) is not None, 'setup_token_required': bool(os.getenv('SETUP_TOKEN')), 'user': data(user, ('password_hash',)) if user else None}


@router.post('/auth/setup', status_code=201)
def setup(body: Credentials, request: Request, db: DB):
    if db.scalar(select(User.id).limit(1)):
        raise HTTPException(409, '已完成初始化')
    required = os.getenv('SETUP_TOKEN')
    if required:
        if not hmac.compare_digest(body.setup_token, required):
            raise HTTPException(403, '初始化凭证无效')
    elif not request.app.state.testing and request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(403, '请在本机初始化')
    user = User(username=body.username, password_hash=password_hash(body.password), is_admin=True)
    db.add(Initialization(id=1))
    db.add(user)
    db.flush()
    return data(user, ('password_hash',))


@router.post('/auth/login')
def login(body: Credentials, request: Request, response: Response, db: DB):
    key = request.client.host
    recent = attempts[key]
    while recent and recent[0] < monotonic() - 300:
        recent.popleft()
    if len(recent) >= 10 and not request.app.state.testing:
        raise HTTPException(429, '尝试过多，请稍后重试')
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify(body.password, user.password_hash):
        recent.append(monotonic())
        raise HTTPException(401, '账号或密码错误')
    recent.clear()
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(timespec='microseconds')
    db.add(LoginSession(token_hash=digest(token), user_id=user.id, expires_at=expires))
    response.set_cookie('sales_session', token, httponly=True, secure=os.getenv('COOKIE_SECURE') == '1', samesite='strict', max_age=43200, path='/')
    return data(user, ('password_hash',))


@router.get('/auth/me')
def me(user: Auth):
    return data(user, ('password_hash',))


@router.post('/auth/logout', status_code=204)
def logout(request: Request, response: Response, db: DB):
    token = request.cookies.get('sales_session', '')
    row = db.get(LoginSession, digest(token))
    if row:
        db.delete(row)
    response.delete_cookie('sales_session', path='/')


@router.post('/users', status_code=201)
def create_user(body: Credentials, user: Auth, db: DB):
    if not user.is_admin:
        raise HTTPException(403, '无管理权限')
    if db.scalar(select(User.id).where(User.username == body.username)):
        raise HTTPException(409, '账号已存在')
    row = User(username=body.username, password_hash=password_hash(body.password))
    db.add(row)
    db.flush()
    return data(row, ('password_hash',))
