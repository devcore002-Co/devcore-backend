from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domains.devos.database import get_db
from domains.devos.models import Budget

router = APIRouter(prefix="/budget", tags=["DevOS · Budget"])


class BudgetUpdate(BaseModel):
    total_balance: float
    currency: str = "GHS"


def _out(b: Budget) -> dict:
    return {
        "total_balance": b.total_balance,
        "currency": b.currency,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }


@router.get("/")
async def get_budget(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Budget).where(Budget.id == 1))
    b = result.scalar_one_or_none()
    if not b:
        return {"total_balance": 0.0, "currency": "GHS", "updated_at": None}
    return _out(b)


@router.put("/")
async def save_budget(body: BudgetUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Budget).where(Budget.id == 1))
    b = result.scalar_one_or_none()
    if b:
        b.total_balance = body.total_balance
        b.currency = body.currency
        b.updated_at = datetime.now(timezone.utc)
    else:
        b = Budget(id=1, total_balance=body.total_balance, currency=body.currency)
        db.add(b)
    await db.flush()
    await db.refresh(b)
    return _out(b)
