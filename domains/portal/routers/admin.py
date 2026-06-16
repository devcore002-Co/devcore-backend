from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from domains.portal.database import get_db
from domains.portal.models import Client, Subscription
from domains.portal.services import auth_service as auth
from domains.portal.services.notification_service import NotificationService
from domains.portal.routers.auth import _client_out

router = APIRouter(prefix="/admin", tags=["Portal · Admin"])


def verify_admin(x_admin_key: str = Header(...)):
    if x_admin_key != get_settings().portal_admin_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")


class ClientCreate(BaseModel):
    name: str
    email: str
    password: str
    business_name: str
    business_type: str
    dashboard: Optional[dict] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    business_name: Optional[str] = None
    business_type: Optional[str] = None


class DashboardUpdate(BaseModel):
    dashboard: dict


class SubscriptionCreate(BaseModel):
    plan: str
    expires_at: Optional[datetime] = None


def _sub_out(s: Subscription) -> dict:
    return {
        "id": s.id,
        "client_id": s.client_id,
        "plan": s.plan,
        "status": s.status,
        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


# ── Clients ───────────────────────────────────────────────────────────────────

@router.get("/clients")
async def list_clients(db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    result = await db.execute(select(Client).order_by(Client.created_at.desc()))
    return [_client_out(c) for c in result.scalars().all()]


@router.post("/clients", status_code=201)
async def create_client(payload: ClientCreate, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    result = await db.execute(select(Client).where(Client.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    client = Client(
        name=payload.name,
        email=payload.email.lower(),
        hashed_password=auth.hash_password(payload.password),
        business_name=payload.business_name,
        business_type=payload.business_type,
        dashboard=payload.dashboard or {},
    )
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return _client_out(client)


@router.get("/clients/{client_id}")
async def get_client(client_id: str, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return _client_out(c)


@router.put("/clients/{client_id}")
async def update_client(client_id: str, payload: ClientUpdate, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    await db.flush()
    await db.refresh(c)
    return _client_out(c)


@router.put("/clients/{client_id}/dashboard")
async def update_dashboard(client_id: str, payload: DashboardUpdate, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    c.dashboard = payload.dashboard
    await db.flush()
    await db.refresh(c)
    return _client_out(c)


@router.put("/clients/{client_id}/activate")
async def activate_client(client_id: str, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    c.is_active = True
    await db.flush()
    return {"detail": "Client activated"}


@router.put("/clients/{client_id}/deactivate")
async def deactivate_client(client_id: str, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    c.is_active = False
    await db.flush()
    return {"detail": "Client deactivated"}


@router.get("/clients/{client_id}/notifications")
async def get_client_notifications(client_id: str, limit: int = 50, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    svc = NotificationService(db)
    notifications = await svc.list(client_id, limit=limit)
    unread = await svc.unread_count(client_id)
    return {"notifications": notifications, "unread_count": unread}


# ── Subscriptions ─────────────────────────────────────────────────────────────

@router.post("/clients/{client_id}/subscription", status_code=201)
async def assign_subscription(client_id: str, payload: SubscriptionCreate, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    result = await db.execute(select(Subscription).where(Subscription.client_id == client_id))
    existing = result.scalar_one_or_none()
    if existing:
        existing.plan = payload.plan
        existing.status = "active"
        existing.expires_at = payload.expires_at
        await db.flush()
        await db.refresh(existing)
        return _sub_out(existing)

    sub = Subscription(client_id=client_id, plan=payload.plan, expires_at=payload.expires_at)
    db.add(sub)
    await db.flush()
    await db.refresh(sub)
    return _sub_out(sub)


@router.put("/clients/{client_id}/subscription/cancel")
async def cancel_subscription(client_id: str, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    result = await db.execute(select(Subscription).where(Subscription.client_id == client_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.status = "cancelled"
    await db.flush()
    return {"detail": "Subscription cancelled"}
