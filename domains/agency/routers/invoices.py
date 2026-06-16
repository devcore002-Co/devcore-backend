from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional
from domains.agency.database import get_db
from domains.agency.models.invoice import Invoice
from domains.agency.models.client import Client

router = APIRouter(prefix="/invoices", tags=["Agency · Invoices"])


class InvoiceItem(BaseModel):
    description: str
    quantity: float = 1
    unit_price: float
    amount: float


class InvoiceCreate(BaseModel):
    client_id: int
    project_id: Optional[int] = None
    items: list[InvoiceItem] = []
    tax_rate: float = 0.0
    currency: str = "GHS"
    due_date: Optional[str] = None
    notes: Optional[str] = None


class InvoiceUpdate(BaseModel):
    items: Optional[list[InvoiceItem]] = None
    tax_rate: Optional[float] = None
    status: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None


def _d(v) -> str | None:
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _out(inv: Invoice) -> dict:
    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "client_id": inv.client_id,
        "client_name": inv.client.name if inv.client else None,
        "project_id": inv.project_id,
        "items": inv.items or [],
        "subtotal": inv.subtotal,
        "tax_rate": inv.tax_rate,
        "tax_amount": inv.tax_amount,
        "total": inv.total,
        "currency": inv.currency,
        "status": inv.status,
        "due_date": _d(inv.due_date),
        "paid_at": _d(inv.paid_at),
        "notes": inv.notes,
        "created_at": _d(inv.created_at),
    }


async def _next_invoice_number(db: AsyncSession) -> str:
    year = date.today().year
    count = await db.scalar(
        select(func.count(Invoice.id)).where(Invoice.invoice_number.like(f"INV-{year}-%"))
    )
    return f"INV-{year}-{(count or 0) + 1:03d}"


def _calc(items: list[InvoiceItem], tax_rate: float) -> tuple[float, float, float]:
    subtotal = sum(i.amount for i in items)
    tax_amount = round(subtotal * tax_rate / 100, 2)
    total = round(subtotal + tax_amount, 2)
    return subtotal, tax_amount, total


@router.get("/")
async def list_invoices(
    client_id: Optional[int] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Invoice).options(selectinload(Invoice.client)).order_by(Invoice.created_at.desc())
    if client_id:
        q = q.where(Invoice.client_id == client_id)
    if status:
        q = q.where(Invoice.status == status)
    result = await db.execute(q)
    return [_out(inv) for inv in result.scalars().all()]


@router.post("/", status_code=201)
async def create_invoice(body: InvoiceCreate, db: AsyncSession = Depends(get_db)):
    client = await db.scalar(select(Client).where(Client.id == body.client_id))
    if not client:
        raise HTTPException(404, "Client not found")
    subtotal, tax_amount, total = _calc(body.items, body.tax_rate)
    inv_number = await _next_invoice_number(db)
    inv = Invoice(
        invoice_number=inv_number,
        client_id=body.client_id,
        project_id=body.project_id,
        items=[i.model_dump() for i in body.items],
        subtotal=subtotal,
        tax_rate=body.tax_rate,
        tax_amount=tax_amount,
        total=total,
        currency=body.currency,
        status="draft",
        due_date=date.fromisoformat(body.due_date) if body.due_date else None,
        notes=body.notes,
    )
    db.add(inv)
    await db.flush()
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.client)).where(Invoice.id == inv.id)
    )
    return _out(result.scalar_one())


@router.get("/{invoice_id}")
async def get_invoice(invoice_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.client)).where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    return _out(inv)


@router.patch("/{invoice_id}")
async def update_invoice(invoice_id: int, body: InvoiceUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.client)).where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv.status == "paid":
        raise HTTPException(400, "Cannot edit a paid invoice")
    if body.items is not None:
        inv.items = [i.model_dump() for i in body.items]
        tax = body.tax_rate if body.tax_rate is not None else inv.tax_rate
        inv.subtotal, inv.tax_amount, inv.total = _calc(body.items, tax)
    if body.tax_rate is not None:
        inv.tax_rate = body.tax_rate
        items = [InvoiceItem(**i) for i in (inv.items or [])]
        inv.subtotal, inv.tax_amount, inv.total = _calc(items, body.tax_rate)
    if body.status is not None:
        inv.status = body.status
    if body.due_date is not None:
        inv.due_date = date.fromisoformat(body.due_date)
    if body.notes is not None:
        inv.notes = body.notes
    await db.flush()
    await db.refresh(inv)
    return _out(inv)


@router.post("/{invoice_id}/mark-paid")
async def mark_paid(invoice_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.client)).where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    inv.status = "paid"
    inv.paid_at = datetime.now(timezone.utc)
    await db.flush()
    return _out(inv)


@router.post("/{invoice_id}/mark-sent")
async def mark_sent(invoice_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.client)).where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv.status == "paid":
        raise HTTPException(400, "Invoice is already paid")
    inv.status = "sent"
    await db.flush()
    return _out(inv)


@router.delete("/{invoice_id}", status_code=204)
async def delete_invoice(invoice_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv.status == "paid":
        raise HTTPException(400, "Cannot delete a paid invoice")
    await db.delete(inv)
