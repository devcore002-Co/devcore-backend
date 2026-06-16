from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from domains.trading.database import get_db
from domains.trading.models.commission import Commission
from domains.trading.models.payout import Payout
from domains.trading.models.client_activity import ClientActivity
from domains.trading.schemas.commission import (
    ActivityCreate, ActivityOut,
    CommissionCreate, CommissionOut,
    PayoutCreate, PayoutOut,
)

router = APIRouter(tags=["Trading · Commissions"])


@router.post("/activity", response_model=ActivityOut, status_code=201)
async def log_activity(body: ActivityCreate, db: AsyncSession = Depends(get_db)):
    data = body.model_dump()
    if data.get("lots_traded") and data.get("commission_per_lot"):
        data["commission_earned"] = round(data["lots_traded"] * data["commission_per_lot"], 2)
        data["is_active"] = data["lots_traded"] > 0
    elif data.get("fees_usd") and data.get("commission_pct"):
        data["commission_earned"] = round(data["fees_usd"] * data["commission_pct"] / 100, 2)
    activity = ClientActivity(**data)
    db.add(activity)
    await db.flush()
    await db.refresh(activity)
    return activity


@router.get("/activity/{client_id}", response_model=list[ActivityOut])
async def get_client_activity(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ClientActivity)
        .where(ClientActivity.client_id == client_id)
        .order_by(ClientActivity.period_month.desc())
    )
    return result.scalars().all()


@router.post("/commissions", response_model=CommissionOut, status_code=201)
async def log_commission(body: CommissionCreate, db: AsyncSession = Depends(get_db)):
    commission = Commission(**body.model_dump())
    db.add(commission)
    await db.flush()
    await db.refresh(commission)
    return commission


@router.get("/commissions", response_model=list[CommissionOut])
async def list_commissions(
    platform_id: int | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Commission).order_by(Commission.period_month.desc())
    if platform_id:
        q = q.where(Commission.platform_id == platform_id)
    if status:
        q = q.where(Commission.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/commissions/summary")
async def commissions_summary(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            Commission.platform_id,
            Commission.status,
            func.sum(Commission.total_amount).label("total"),
            func.count(Commission.id).label("months"),
        ).group_by(Commission.platform_id, Commission.status)
    )
    rows = result.all()
    summary: dict = {}
    for row in rows:
        pid = str(row.platform_id)
        if pid not in summary:
            summary[pid] = {}
        summary[pid][row.status] = {"total_usd": float(row.total), "months": row.months}
    return summary


@router.patch("/commissions/{commission_id}/mark-paid")
async def mark_commission_paid(commission_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Commission).where(Commission.id == commission_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Commission not found")
    c.status = "paid"
    return {"message": "Marked as paid", "id": commission_id}


@router.post("/payouts", response_model=PayoutOut, status_code=201)
async def log_payout(body: PayoutCreate, db: AsyncSession = Depends(get_db)):
    payout = Payout(**body.model_dump())
    db.add(payout)
    await db.flush()
    await db.refresh(payout)
    return payout


@router.get("/payouts", response_model=list[PayoutOut])
async def list_payouts(platform_id: int | None = None, db: AsyncSession = Depends(get_db)):
    q = select(Payout).order_by(Payout.payout_date.desc())
    if platform_id:
        q = q.where(Payout.platform_id == platform_id)
    result = await db.execute(q)
    return result.scalars().all()
