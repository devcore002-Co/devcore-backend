from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domains.trading.database import get_db
from domains.trading.models.referred_client import ReferredClient
from domains.trading.schemas.referral import ReferralCreate, ReferralUpdate, ReferralOut

router = APIRouter(prefix="/referrals", tags=["Trading · Referrals"])

_STATUSES = ("pending", "registered", "active", "inactive", "churned")


@router.post("/", response_model=ReferralOut, status_code=201)
async def create_referral(body: ReferralCreate, db: AsyncSession = Depends(get_db)):
    client = ReferredClient(**body.model_dump())
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return client


@router.get("/", response_model=list[ReferralOut])
async def list_referrals(
    platform_id: int | None = None,
    status: str | None = None,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(ReferredClient).order_by(ReferredClient.referral_date.desc())
    if platform_id:
        q = q.where(ReferredClient.platform_id == platform_id)
    if status:
        q = q.where(ReferredClient.status == status)
    if source:
        q = q.where(ReferredClient.source == source)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/active", response_model=list[ReferralOut])
async def active_clients(platform_id: int | None = None, db: AsyncSession = Depends(get_db)):
    q = select(ReferredClient).where(ReferredClient.status == "active")
    if platform_id:
        q = q.where(ReferredClient.platform_id == platform_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{referral_id}", response_model=ReferralOut)
async def get_referral(referral_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ReferredClient).where(ReferredClient.id == referral_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Referral not found")
    return client


@router.patch("/{referral_id}", response_model=ReferralOut)
async def update_referral(referral_id: int, body: ReferralUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ReferredClient).where(ReferredClient.id == referral_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Referral not found")
    if body.status and body.status not in _STATUSES:
        raise HTTPException(400, f"Status must be one of: {_STATUSES}")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(client, field, value)
    return client
