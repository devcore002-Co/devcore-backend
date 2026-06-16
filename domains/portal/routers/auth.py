from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from domains.portal.database import get_db
from domains.portal.models import Client
from domains.portal.services import auth_service as auth
from domains.portal.services.email_service import EmailService
from domains.portal.services.notification_service import NotificationService
from domains.portal.services.push_service import PushService

router = APIRouter(prefix="/auth", tags=["Portal · Auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class MagicLinkRequest(BaseModel):
    email: str


class MagicLinkVerify(BaseModel):
    token: str


class MagicPollRequest(BaseModel):
    request_id: str


class GoogleAuthRequest(BaseModel):
    id_token: str


def _s():
    return get_settings()


@router.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.email == payload.email.lower()))
    client = result.scalar_one_or_none()
    if not client or not auth.verify_password(payload.password, client.hashed_password or ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not client.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")
    client.last_login_at = datetime.now(timezone.utc)
    await db.flush()
    return auth.create_tokens(client.id)


@router.post("/magic-link")
async def request_magic_link(payload: MagicLinkRequest, db: AsyncSession = Depends(get_db)):
    s = _s()
    token = auth.create_magic_token(payload.email)
    session = await auth.create_magic_session(db, payload.email)
    link = f"{s.portal_api_base_url}/portal/auth/open?token={token}"
    await EmailService().send_magic_link(payload.email, link)
    return {"detail": "If an account is eligible, a sign-in link has been sent.", "request_id": session.id}


@router.get("/open", response_class=HTMLResponse)
async def open_app(token: str, db: AsyncSession = Depends(get_db)):
    s = _s()
    email = auth.verify_magic_token(token)
    if email:
        await auth.mark_magic_session_verified(db, email)

    deep_link = f"{s.magic_link_scheme}?token={token}"
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Verify your DevCore account</title>
</head>
<body style="font-family: -apple-system, Helvetica, Arial, sans-serif; background:#0f172a; margin:0; padding:32px; display:flex; align-items:center; justify-content:center; min-height:100vh;">
  <div style="max-width:420px; width:100%; background:#1e293b; border-radius:16px; padding:32px; text-align:center;">
    <div id="loading">
      <h1 style="color:#fff; font-size:20px; margin:0 0 12px;">Opening DevCore…</h1>
      <p style="color:#94a3b8; font-size:14px; line-height:20px; margin:0 0 24px;">
        If the app doesn't open automatically, tap the button below.
      </p>
      <a href="{deep_link}"
         style="display:inline-block; background:#6366f1; color:#fff; text-decoration:none;
                font-weight:700; font-size:15px; padding:14px 32px; border-radius:12px;">
        Open DevCore
      </a>
    </div>
    <div id="fallback" style="display:none;">
      <h1 style="color:#fff; font-size:20px; margin:0 0 12px;">You're verified ✅</h1>
      <p style="color:#94a3b8; font-size:14px; line-height:20px; margin:0;">
        It looks like DevCore isn't installed on this device, but that's okay &mdash;
        head back to the DevCore app on your phone and it'll sign you in
        automatically within a few seconds.
      </p>
    </div>
  </div>
  <script>
    var left = false;
    window.addEventListener('blur', function () {{ left = true; }});
    document.addEventListener('visibilitychange', function () {{
      if (document.hidden) left = true;
    }});
    window.location.replace("{deep_link}");
    setTimeout(function () {{
      if (!left) {{
        document.getElementById('loading').style.display = 'none';
        document.getElementById('fallback').style.display = 'block';
      }}
    }}, 1800);
  </script>
</body>
</html>"""


@router.post("/verify")
async def verify_magic_link(payload: MagicLinkVerify, db: AsyncSession = Depends(get_db)):
    email = auth.verify_magic_token(payload.token)
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired link")
    client, created = await auth.get_or_create_by_email(db, email)
    await auth.mark_magic_session_verified(db, email)
    return await _complete_login(db, client, created)


@router.post("/poll")
async def poll_magic_link(payload: MagicPollRequest, db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timezone
    session = await auth.get_magic_session(db, payload.request_id)
    if not session or session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This sign-in request has expired")
    if not session.verified:
        return {"verified": False}
    client, created = await auth.get_or_create_by_email(db, session.email)
    await auth.delete_magic_session(db, session)
    tokens = await _complete_login(db, client, created)
    return {"verified": True, **tokens}


@router.post("/google")
async def google_sign_in(payload: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    s = _s()
    if not s.google_client_ids_list:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is not configured")
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token
        claims = google_id_token.verify_oauth2_token(payload.id_token, google_requests.Request())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token")

    if claims.get("aud") not in s.google_client_ids_list:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token")

    email = claims.get("email")
    if not email or not claims.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google account email not verified")

    client, created = await auth.get_or_create_by_email(db, email.lower())
    if created and claims.get("name"):
        client.name = claims["name"]
        await db.flush()

    return await _complete_login(db, client, created)


@router.post("/refresh")
async def refresh(refresh_token: str, db: AsyncSession = Depends(get_db)):
    client_id = auth.verify_refresh_token(refresh_token)
    if not client_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client or not client.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Client not found")
    return auth.create_tokens(client_id)


@router.get("/me")
async def me(client: Client = Depends(auth.get_current_client)):
    return _client_out(client)


def _client_out(c: Client) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "business_name": c.business_name,
        "business_type": c.business_type,
        "is_active": c.is_active,
        "fcm_token": c.fcm_token,
        "last_login_at": c.last_login_at.isoformat() if c.last_login_at else None,
        "dashboard": c.dashboard,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


async def _complete_login(db: AsyncSession, client: Client, created: bool) -> dict:
    s = _s()
    if not client.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")
    client.last_login_at = datetime.now(timezone.utc)
    await db.flush()
    if created and client.email not in s.chief_emails_list:
        await _notify_chiefs_of_new_client(db, client)
    return auth.create_tokens(client.id)


async def _notify_chiefs_of_new_client(db: AsyncSession, client: Client) -> None:
    s = _s()
    result = await db.execute(select(Client).where(Client.email.in_(s.chief_emails_list)))
    chiefs = result.scalars().all()
    svc = NotificationService(db)
    push = PushService()
    for chief in chiefs:
        n = await svc.create(
            client_id=chief.id,
            title="New client signed up",
            body=f"{client.email} just created an account. Set up their dashboard in DevOS.",
            type="alert",
            source="signup",
            data={"new_client_id": client.id, "new_client_email": client.email},
        )
        if chief.fcm_token:
            await push.send(token=chief.fcm_token, title=n.title, body=n.body, data={"notification_id": n.id})
