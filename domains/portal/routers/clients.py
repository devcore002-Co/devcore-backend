from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.portal.database import get_db
from domains.portal.models import Client, Subscription
from domains.portal.services.auth_service import get_current_client
from domains.portal.routers.auth import _client_out

router = APIRouter(prefix="/clients", tags=["Portal · Clients"])


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    business_name: Optional[str] = None
    business_type: Optional[str] = None


class FCMUpdate(BaseModel):
    fcm_token: str


class SubscriptionCreate(BaseModel):
    plan: str
    expires_at: Optional[str] = None


@router.get("/me")
async def get_me(client: Client = Depends(get_current_client)):
    return _client_out(client)


@router.put("/me")
async def update_me(
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(client, k, v)
    await db.flush()
    await db.refresh(client)
    return _client_out(client)


@router.put("/me/fcm-token")
async def update_fcm_token(
    payload: FCMUpdate,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    client.fcm_token = payload.fcm_token
    await db.flush()
    return {"detail": "FCM token updated"}


@router.post("/me/subscription", status_code=201)
async def create_subscription(
    payload: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    result = await db.execute(select(Subscription).where(Subscription.client_id == client.id))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Subscription already exists")

    sub = Subscription(client_id=client.id, plan=payload.plan, expires_at=payload.expires_at)
    db.add(sub)
    await db.flush()
    await db.refresh(sub)
    return {
        "id": sub.id,
        "client_id": sub.client_id,
        "plan": sub.plan,
        "status": sub.status,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
    }
