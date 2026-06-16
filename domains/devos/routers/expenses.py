from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domains.devos.database import get_db
from domains.devos.models import Expense

router = APIRouter(prefix="/expenses", tags=["DevOS · Expenses"])


class ExpenseCreate(BaseModel):
    expense_date: str
    amount: float
    currency: str = "GHS"
    category: str
    payment_method: str
    description: str
    notes: Optional[str] = None


class ExpenseUpdate(BaseModel):
    expense_date: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    category: Optional[str] = None
    payment_method: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None


def _out(e: Expense) -> dict:
    return {
        "id": e.id,
        "expense_date": e.expense_date,
        "amount": e.amount,
        "currency": e.currency,
        "category": e.category,
        "payment_method": e.payment_method,
        "description": e.description,
        "notes": e.notes,
        "status": e.status,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.get("/")
async def list_expenses(
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    payment_method: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
):
    q = select(Expense).order_by(Expense.expense_date.desc(), Expense.created_at.desc()).limit(limit)
    if category:
        q = q.where(Expense.category == category)
    if date_from:
        q = q.where(Expense.expense_date >= date_from)
    if date_to:
        q = q.where(Expense.expense_date <= date_to)
    if payment_method:
        q = q.where(Expense.payment_method == payment_method)
    if search:
        q = q.where(Expense.description.ilike(f"%{search}%"))
    result = await db.execute(q)
    return [_out(e) for e in result.scalars().all()]


@router.post("/", status_code=201)
async def create_expense(body: ExpenseCreate, db: AsyncSession = Depends(get_db)):
    e = Expense(**body.model_dump())
    db.add(e)
    await db.flush()
    await db.refresh(e)
    return _out(e)


@router.get("/{expense_id}")
async def get_expense(expense_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(404, "Expense not found")
    return _out(e)


@router.patch("/{expense_id}")
async def update_expense(expense_id: str, body: ExpenseUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(404, "Expense not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(e, k, v)
    await db.flush()
    await db.refresh(e)
    return _out(e)


@router.delete("/{expense_id}", status_code=204)
async def delete_expense(expense_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(404, "Expense not found")
    await db.delete(e)
