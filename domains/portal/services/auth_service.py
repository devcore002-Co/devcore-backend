import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from domains.portal.database import get_db
from domains.portal.models import Client, MagicSession

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer()


def _now():
    return datetime.now(timezone.utc)


def _s():
    return get_settings()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(client_id: str, expires_delta: timedelta, token_type: str = "access") -> str:
    s = _s()
    payload = {
        "sub":  client_id,
        "type": token_type,
        "exp":  _now() + expires_delta,
    }
    return jwt.encode(payload, s.secret_key, algorithm=s.algorithm)


def create_tokens(client_id: str) -> dict:
    s = _s()
    access  = create_token(client_id, timedelta(minutes=s.access_token_expire_minutes), "access")
    refresh = create_token(client_id, timedelta(days=s.refresh_token_expire_days), "refresh")
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


def verify_access_token(token: str) -> Optional[str]:
    s = _s()
    try:
        payload = jwt.decode(token, s.secret_key, algorithms=[s.algorithm])
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def verify_refresh_token(token: str) -> Optional[str]:
    s = _s()
    try:
        payload = jwt.decode(token, s.secret_key, algorithms=[s.algorithm])
        if payload.get("type") != "refresh":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def create_magic_token(email: str) -> str:
    s = _s()
    payload = {
        "sub":  email.lower(),
        "type": "magic",
        "exp":  _now() + timedelta(minutes=s.magic_link_expire_minutes),
    }
    return jwt.encode(payload, s.secret_key, algorithm=s.algorithm)


def verify_magic_token(token: str) -> Optional[str]:
    s = _s()
    try:
        payload = jwt.decode(token, s.secret_key, algorithms=[s.algorithm])
        if payload.get("type") != "magic":
            return None
        return payload.get("sub")
    except JWTError:
        return None


async def create_magic_session(db: AsyncSession, email: str) -> MagicSession:
    s = _s()
    email = email.lower()
    await db.execute(delete(MagicSession).where(MagicSession.email == email))
    session = MagicSession(
        email=email,
        expires_at=_now() + timedelta(minutes=s.magic_link_expire_minutes),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def mark_magic_session_verified(db: AsyncSession, email: str) -> None:
    email = email.lower()
    result = await db.execute(
        select(MagicSession)
        .where(MagicSession.email == email, MagicSession.expires_at >= _now())
        .order_by(MagicSession.created_at.desc())
    )
    session = result.scalar_one_or_none()
    if session:
        session.verified = True
        await db.flush()


async def get_magic_session(db: AsyncSession, request_id: str) -> Optional[MagicSession]:
    result = await db.execute(select(MagicSession).where(MagicSession.id == request_id))
    return result.scalar_one_or_none()


async def delete_magic_session(db: AsyncSession, session: MagicSession) -> None:
    await db.delete(session)
    await db.flush()


async def get_or_create_by_email(db: AsyncSession, email: str) -> tuple[Client, bool]:
    """Returns (client, created). Auto-creates chief or generic account on first magic-link login."""
    s = _s()
    email = email.lower()
    result = await db.execute(select(Client).where(Client.email == email))
    client = result.scalar_one_or_none()
    if client:
        return client, False

    if email in s.chief_emails_list:
        client = Client(
            name=email.split("@")[0],
            email=email,
            hashed_password=hash_password(uuid.uuid4().hex),
            business_name=s.chief_business_name,
            business_type="service",
            dashboard={"dashboard_url": s.chief_dashboard_url} if s.chief_dashboard_url else {},
        )
    else:
        client = Client(
            name=email.split("@")[0],
            email=email,
            hashed_password=hash_password(uuid.uuid4().hex),
            business_name="New Client",
            business_type="service",
            dashboard={},
        )
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return client, True


async def get_current_client(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> Client:
    client_id = verify_access_token(credentials.credentials)
    if not client_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client or not client.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Client not found")
    return client
