from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from domains.devos.database import get_db
from domains.devos.models import Income

router = APIRouter(prefix="/income", tags=["DevOS · Income"])


class IncomeCreate(BaseModel):
    income_date: str
    amount: float
    currency: str = "GHS"
    source: str
    notes: Optional[str] = None


def _out(i: Income) -> dict:
    return {
        "id": i.id,
        "income_date": i.income_date,
        "amount": i.amount,
        "currency": i.currency,
        "source": i.source,
        "notes": i.notes,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


@router.get("/")
async def list_income(limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Income).order_by(Income.income_date.desc()).limit(limit)
    )
    return [_out(i) for i in result.scalars().all()]


@router.post("/", status_code=201)
async def create_income(body: IncomeCreate, db: AsyncSession = Depends(get_db)):
    i = Income(**body.model_dump())
    db.add(i)
    await db.flush()
    await db.refresh(i)
    return _out(i)


@router.delete("/{income_id}", status_code=204)
async def delete_income(income_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Income).where(Income.id == income_id))
    i = result.scalar_one_or_none()
    if not i:
        raise HTTPException(404, "Income record not found")
    await db.delete(i)


@router.get("/summary")
async def income_summary(db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.sum(Income.amount))) or 0
    count = await db.scalar(select(func.count(Income.id))) or 0
    return {"total_ghs": round(float(total), 2), "count": count}
