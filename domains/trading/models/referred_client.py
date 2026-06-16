from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from domains.trading.database import Base


class ReferredClient(Base):
    __tablename__ = "referred_clients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("trading_platforms.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client_platform_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    referral_date: Mapped[date] = mapped_column(Date)
    registered_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    first_trade_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    campaign: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    platform: Mapped["TradingPlatform"] = relationship("TradingPlatform", back_populates="referred_clients")
    activity_logs: Mapped[list["ClientActivity"]] = relationship("ClientActivity", back_populates="client")
