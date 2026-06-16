from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from domains.trading.database import Base


class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("trading_platforms.id"), index=True)
    period_month: Mapped[date] = mapped_column(Date, index=True)
    total_lots: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission_per_lot: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_volume_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    active_clients: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    platform: Mapped["TradingPlatform"] = relationship("TradingPlatform", back_populates="commissions")
