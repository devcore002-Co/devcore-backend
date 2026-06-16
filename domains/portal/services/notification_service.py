from typing import Any, Dict, List, Optional
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from domains.portal.models import Notification


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        client_id: str,
        title: str,
        body: str,
        type: str = "info",
        source: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        n = Notification(client_id=client_id, title=title, body=body, type=type, source=source, data=data)
        self.db.add(n)
        await self.db.flush()
        await self.db.refresh(n)
        return n

    async def list(self, client_id: str, limit: int = 50, offset: int = 0) -> List[Notification]:
        result = await self.db.execute(
            select(Notification)
            .where(Notification.client_id == client_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def unread_count(self, client_id: str) -> int:
        count = await self.db.scalar(
            select(func.count(Notification.id)).where(
                Notification.client_id == client_id,
                Notification.is_read == False,
            )
        )
        return count or 0

    async def mark_read(self, notification_id: str, client_id: str) -> bool:
        result = await self.db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.client_id == client_id,
            )
        )
        n = result.scalar_one_or_none()
        if not n:
            return False
        n.is_read = True
        await self.db.flush()
        return True

    async def mark_all_read(self, client_id: str) -> None:
        await self.db.execute(
            update(Notification)
            .where(Notification.client_id == client_id, Notification.is_read == False)
            .values(is_read=True)
        )
        await self.db.flush()
