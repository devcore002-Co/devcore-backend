from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from domains.agency.database import get_db
from domains.agency.models.client import Client

router = APIRouter(prefix="/clients", tags=["Agency · Clients"])


class ClientCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


def _out(c: Client) -> dict:
    return {
        "id": c.id, "name": c.name, "email": c.email,
        "phone": c.phone, "company": c.company,
        "address": c.address, "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/")
async def list_clients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).order_by(Client.name))
    return [_out(c) for c in result.scalars().all()]


@router.post("/", status_code=201)
async def create_client(body: ClientCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Client).where(Client.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Email already registered")
    c = Client(**body.model_dump())
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return _out(c)


@router.get("/{client_id}")
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Client not found")
    return _out(c)


@router.patch("/{client_id}")
async def update_client(client_id: int, body: ClientUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Client not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    await db.flush()
    await db.refresh(c)
    return _out(c)


@router.delete("/{client_id}", status_code=204)
async def delete_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Client not found")
    await db.delete(c)
