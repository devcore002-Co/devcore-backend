from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domains.trading.database import get_db
from domains.trading.models.trading_platform import TradingPlatform
from domains.trading.schemas.platform import PlatformCreate, PlatformUpdate, PlatformOut

router = APIRouter(prefix="/platforms", tags=["Trading · Platforms"])


@router.post("/", response_model=PlatformOut, status_code=201)
async def create_platform(body: PlatformCreate, db: AsyncSession = Depends(get_db)):
    platform = TradingPlatform(**body.model_dump())
    db.add(platform)
    await db.flush()
    await db.refresh(platform)
    return platform


@router.get("/", response_model=list[PlatformOut])
async def list_platforms(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TradingPlatform).order_by(TradingPlatform.name))
    return result.scalars().all()


@router.get("/{platform_id}", response_model=PlatformOut)
async def get_platform(platform_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TradingPlatform).where(TradingPlatform.id == platform_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Platform not found")
    return p


@router.patch("/{platform_id}", response_model=PlatformOut)
async def update_platform(platform_id: int, body: PlatformUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TradingPlatform).where(TradingPlatform.id == platform_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Platform not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    return p
