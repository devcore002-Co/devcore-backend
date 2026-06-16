import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from domains.portal.database import get_db
from domains.portal.models import Client, WebhookLog
from domains.portal.services.notification_service import NotificationService
from domains.portal.services.push_service import PushService

logger = logging.getLogger("devcore-portal")
router = APIRouter(prefix="/webhooks", tags=["Portal · Webhooks"])


class WebhookPayload(BaseModel):
    client_id: str
    event_type: str
    title: str
    body: str
    type: str = "info"
    source: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


def verify_webhook_secret(x_webhook_secret: str = Header(...)):
    s = get_settings()
    if s.portal_webhook_secret and x_webhook_secret != s.portal_webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")


@router.post("/trigger", status_code=202)
async def trigger(
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_webhook_secret),
):
    log = WebhookLog(
        source=payload.source or "devos",
        event_type=payload.event_type,
        client_id=payload.client_id,
        payload=payload.model_dump(),
    )
    db.add(log)

    result = await db.execute(
        select(Client).where(Client.id == payload.client_id, Client.is_active == True)
    )
    client = result.scalar_one_or_none()

    if not client:
        log.status = "failed"
        log.error = "Client not found or inactive"
        await db.flush()
        raise HTTPException(status_code=404, detail="Client not found")

    n = await NotificationService(db).create(
        client_id=payload.client_id,
        title=payload.title,
        body=payload.body,
        type=payload.type,
        source=payload.source,
        data=payload.data,
    )

    if client.fcm_token:
        await PushService().send(
            token=client.fcm_token,
            title=payload.title,
            body=payload.body,
            data={"notification_id": n.id, **(payload.data or {})},
        )

    log.status = "processed"
    log.processed_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info(f"Webhook processed: {payload.event_type} → client {payload.client_id}")
    return {"detail": "Notification delivered", "notification_id": n.id}
