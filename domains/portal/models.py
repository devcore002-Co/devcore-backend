import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import relationship
from domains.portal.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


class Client(Base):
    __tablename__ = "clients"

    id              = Column(String, primary_key=True, default=_uuid)
    name            = Column(String, nullable=False)
    email           = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)
    business_name   = Column(String, nullable=False)
    business_type   = Column(Enum("service", "commerce", "hybrid", name="business_type"), nullable=False)
    is_active       = Column(Boolean, default=True)
    fcm_token       = Column(String, nullable=True)
    last_login_at   = Column(DateTime(timezone=True), nullable=True)
    dashboard       = Column(JSON, nullable=True, default=dict)
    created_at      = Column(DateTime(timezone=True), default=_now)
    updated_at      = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    notifications = relationship("Notification", back_populates="client", cascade="all, delete-orphan", lazy="select")
    subscription  = relationship("Subscription", back_populates="client", uselist=False, cascade="all, delete-orphan", lazy="select")


class Notification(Base):
    __tablename__ = "notifications"

    id         = Column(String, primary_key=True, default=_uuid)
    client_id  = Column(String, ForeignKey("clients.id"), nullable=False, index=True)
    title      = Column(String, nullable=False)
    body       = Column(Text, nullable=False)
    type       = Column(Enum("info", "alert", "update", "order", "booking", name="notification_type"), default="info")
    is_read    = Column(Boolean, default=False)
    data       = Column(JSON, nullable=True)
    source     = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    client = relationship("Client", back_populates="notifications")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id         = Column(String, primary_key=True, default=_uuid)
    client_id  = Column(String, ForeignKey("clients.id"), unique=True, nullable=False)
    plan       = Column(Enum("monthly", "annual", name="subscription_plan"), nullable=False)
    status     = Column(Enum("active", "expired", "cancelled", name="subscription_status"), default="active")
    started_at = Column(DateTime(timezone=True), default=_now)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    client = relationship("Client", back_populates="subscription")


class MagicSession(Base):
    __tablename__ = "magic_sessions"

    id         = Column(String, primary_key=True, default=_uuid)
    email      = Column(String, nullable=False, index=True)
    verified   = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)


class WebhookLog(Base):
    __tablename__ = "webhook_logs"

    id           = Column(String, primary_key=True, default=_uuid)
    source       = Column(String, nullable=False)
    event_type   = Column(String, nullable=False)
    client_id    = Column(String, nullable=True)
    payload      = Column(JSON, nullable=True)
    status       = Column(Enum("received", "processed", "failed", name="webhook_status"), default="received")
    error        = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at   = Column(DateTime(timezone=True), default=_now)
