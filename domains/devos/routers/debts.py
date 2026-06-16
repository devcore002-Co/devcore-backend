from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domains.devos.database import get_db
from domains.devos.models import Debt, DebtPayment

router = APIRouter(prefix="/debts", tags=["DevOS · Debts"])


class DebtCreate(BaseModel):
    person_name: str
    description: str
    total_amount: float
    currency: str = "GHS"
    date_lent: str
    notes: Optional[str] = None


class DebtUpdate(BaseModel):
    person_name: Optional[str] = None
    description: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    date_lent: Optional[str] = None
    notes: Optional[str] = None


class PaymentCreate(BaseModel):
    amount: float
    payment_date: str
    notes: Optional[str] = None


def _payment_out(p: DebtPayment) -> dict:
    return {
        "id": p.id,
        "debt_id": p.debt_id,
        "amount": p.amount,
        "payment_date": p.payment_date,
        "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _out(d: Debt) -> dict:
    paid = sum(p.amount for p in (d.payments or []))
    return {
        "id": d.id,
        "person_name": d.person_name,
        "description": d.description,
        "total_amount": d.total_amount,
        "currency": d.currency,
        "date_lent": d.date_lent,
        "notes": d.notes,
        "status": d.status,
        "amount_paid": paid,
        "amount_remaining": round(d.total_amount - paid, 2),
        "payments": [_payment_out(p) for p in (d.payments or [])],
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.get("/")
async def list_debts(show_paid: bool = False, db: AsyncSession = Depends(get_db)):
    q = select(Debt).order_by(Debt.date_lent.desc())
    if not show_paid:
        q = q.where(Debt.status == "active")
    result = await db.execute(q)
    return [_out(d) for d in result.scalars().all()]


@router.post("/", status_code=201)
async def create_debt(body: DebtCreate, db: AsyncSession = Depends(get_db)):
    d = Debt(**body.model_dump())
    db.add(d)
    await db.flush()
    await db.refresh(d)
    return _out(d)


@router.get("/{debt_id}")
async def get_debt(debt_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Debt).where(Debt.id == debt_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Debt not found")
    return _out(d)


@router.patch("/{debt_id}")
async def update_debt(debt_id: str, body: DebtUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Debt).where(Debt.id == debt_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Debt not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(d, k, v)
    await db.flush()
    await db.refresh(d)
    return _out(d)


@router.delete("/{debt_id}", status_code=204)
async def delete_debt(debt_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Debt).where(Debt.id == debt_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Debt not found")
    await db.delete(d)


@router.post("/{debt_id}/payments", status_code=201)
async def add_payment(debt_id: str, body: PaymentCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Debt).where(Debt.id == debt_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Debt not found")
    p = DebtPayment(debt_id=debt_id, **body.model_dump())
    db.add(p)
    await db.flush()
    await db.refresh(d)
    paid = sum(pay.amount for pay in (d.payments or []))
    if paid >= d.total_amount:
        d.status = "paid"
    return _out(d)


@router.delete("/payments/{payment_id}", status_code=204)
async def delete_payment(payment_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DebtPayment).where(DebtPayment.id == payment_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Payment not found")
    await db.delete(p)


@router.get("/summary/totals")
async def debt_summary(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Debt).where(Debt.status == "active"))
    debts = result.scalars().all()
    total_lent = sum(d.total_amount for d in debts)
    total_paid = sum(sum(p.amount for p in (d.payments or [])) for d in debts)
    return {
        "active_debts": len(debts),
        "total_lent_ghs": round(total_lent, 2),
        "total_paid_ghs": round(total_paid, 2),
        "total_remaining_ghs": round(total_lent - total_paid, 2),
    }
