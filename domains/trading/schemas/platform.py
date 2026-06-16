from pydantic import BaseModel


class PlatformCreate(BaseModel):
    name: str
    platform_type: str
    commission_type: str = "unknown"
    commission_rate: float | None = None
    commission_currency: str = "USD"
    ib_account_id: str | None = None
    affiliate_link: str | None = None
    dashboard_url: str | None = None
    track_active_clients: bool = False
    notes: str | None = None


class PlatformUpdate(BaseModel):
    commission_type: str | None = None
    commission_rate: float | None = None
    affiliate_link: str | None = None
    track_active_clients: bool | None = None
    notes: str | None = None
    is_active: bool | None = None


class PlatformOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str
    platform_type: str
    commission_type: str
    commission_rate: float | None
    commission_currency: str
    ib_account_id: str | None
    affiliate_link: str | None
    track_active_clients: bool
    is_active: bool
