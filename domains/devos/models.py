import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from domains.devos.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(String, primary_key=True, default=_uuid)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expense_date = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="GHS", nullable=False)
    category = Column(String, nullable=False)
    payment_method = Column(String, nullable=False)
    description = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String, default="submitted", nullable=False)


class Debt(Base):
    __tablename__ = "debts"

    id = Column(String, primary_key=True, default=_uuid)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    person_name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    total_amount = Column(Float, nullable=False)
    currency = Column(String, default="GHS", nullable=False)
    date_lent = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String, default="active", nullable=False)

    payments = relationship(
        "DebtPayment", back_populates="debt",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DebtPayment(Base):
    __tablename__ = "debt_payments"

    id = Column(String, primary_key=True, default=_uuid)
    debt_id = Column(String, ForeignKey("debts.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_date = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    debt = relationship("Debt", back_populates="payments")


class Income(Base):
    __tablename__ = "income"

    id = Column(String, primary_key=True, default=_uuid)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    income_date = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="GHS", nullable=False)
    source = Column(String, nullable=False)
    notes = Column(Text, nullable=True)


class Budget(Base):
    __tablename__ = "budget"

    id = Column(Integer, primary_key=True, default=1)
    total_balance = Column(Float, nullable=False, default=0.0)
    currency = Column(String, default="GHS", nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id = Column(String, primary_key=True, default=_uuid)
    client = Column(String(100), nullable=False)
    platforms = Column(JSON, nullable=False)
    content_type = Column(String(50), default="post")
    caption = Column(Text, nullable=False)
    hashtags = Column(Text, nullable=True)
    prompt_used = Column(Text, nullable=True)
    media_url = Column(String(500), nullable=True)
    media_public_id = Column(String(255), nullable=True)
    media_type = Column(String(20), default="image")
    scheduled_at = Column(DateTime, nullable=False)
    status = Column(String(20), default="scheduled")
    published_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
