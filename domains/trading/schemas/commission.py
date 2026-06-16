from datetime import date as DateType
from pydantic import BaseModel


class ActivityCreate(BaseModel):
    client_id: int
    period_month: DateType
    lots_traded: float | None = None
    commission_per_lot: float | None = None
    volume_usd: float | None = None
    fees_usd: float | None = None
    commission_pct: float | None = None
    notes: str | None = None


class ActivityOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    client_id: int
    period_month: DateType
    lots_traded: float | None
    commission_earned: float | None
    volume_usd: float | None
    is_active: bool


class CommissionCreate(BaseModel):
    platform_id: int
    period_month: DateType
    total_lots: float | None = None
    commission_per_lot: float | None = None
    total_volume_usd: float | None = None
    commission_pct: float | None = None
    total_amount: float
    currency: str = "USD"
    active_clients: int = 0
    notes: str | None = None


class CommissionOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    platform_id: int
    period_month: DateType
    total_lots: float | None
    total_amount: float
    currency: str
    active_clients: int
    status: str


class PayoutCreate(BaseModel):
    platform_id: int
    amount: float
    currency: str = "USD"
    payout_date: DateType
    method: str | None = None
    reference: str | None = None
    covers_months: str | None = None
    notes: str | None = None


class PayoutOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    platform_id: int
    amount: float
    currency: str
    payout_date: DateType
    method: str | None
    reference: str | None
    covers_months: str | None
