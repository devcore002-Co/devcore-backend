from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from domains.trading.database import Base


class ClientActivity(Base):
    __tablename__ = "client_activity"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("referred_clients.id"), index=True)
    period_month: Mapped[date] = mapped_column(Date, index=True)
    lots_traded: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission_per_lot: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission_earned: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    client: Mapped["ReferredClient"] = relationship("ReferredClient", back_populates="activity_logs")
