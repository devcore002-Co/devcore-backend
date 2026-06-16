from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from domains.trading.database import Base


class TradingPlatform(Base):
    __tablename__ = "trading_platforms"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    platform_type: Mapped[str] = mapped_column(String(20))
    commission_type: Mapped[str] = mapped_column(String(30), default="unknown")
    commission_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission_currency: Mapped[str] = mapped_column(String(10), default="USD")
    ib_account_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    affiliate_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dashboard_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    track_active_clients: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    referred_clients: Mapped[list["ReferredClient"]] = relationship(
        "ReferredClient", back_populates="platform"
    )
    commissions: Mapped[list["Commission"]] = relationship(
        "Commission", back_populates="platform"
    )
    payouts: Mapped[list["Payout"]] = relationship("Payout", back_populates="platform")
