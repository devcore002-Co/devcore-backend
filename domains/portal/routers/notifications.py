from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from domains.portal.database import get_db
from domains.portal.models import Client
from domains.portal.services.auth_service import get_current_client
from domains.portal.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Portal · Notifications"])


def _out(n) -> dict:
    return {
        "id": n.id,
        "client_id": n.client_id,
        "title": n.title,
        "body": n.body,
        "type": n.type,
        "is_read": n.is_read,
        "data": n.data,
        "source": n.source,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("")
async def get_notifications(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    svc = NotificationService(db)
    notifications = await svc.list(client.id, limit=limit, offset=offset)
    unread = await svc.unread_count(client.id)
    return {"notifications": [_out(n) for n in notifications], "unread_count": unread}


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    await NotificationService(db).mark_read(notification_id, client.id)
    return {"detail": "Marked as read"}


@router.put("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    await NotificationService(db).mark_all_read(client.id)
    return {"detail": "All notifications marked as read"}
