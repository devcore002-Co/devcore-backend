from datetime import date as DateType
from pydantic import BaseModel


class ReferralCreate(BaseModel):
    platform_id: int
    full_name: str
    email: str | None = None
    phone: str | None = None
    country: str | None = None
    client_platform_id: str | None = None
    referral_date: DateType
    registered_date: DateType | None = None
    source: str | None = None
    campaign: str | None = None
    notes: str | None = None


class ReferralUpdate(BaseModel):
    status: str | None = None
    client_platform_id: str | None = None
    registered_date: DateType | None = None
    first_trade_date: DateType | None = None
    notes: str | None = None


class ReferralOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    platform_id: int
    full_name: str
    email: str | None
    phone: str | None
    country: str | None
    client_platform_id: str | None
    status: str
    referral_date: DateType
    registered_date: DateType | None
    first_trade_date: DateType | None
    source: str | None
    campaign: str | None
