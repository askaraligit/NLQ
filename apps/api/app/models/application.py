"""Provisioning metadata, intentionally inaccessible to analytics readers."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps


class Tenant(Timestamps, Base):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "app", "comment": "Organizations that own isolated ERP data."}

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)


class AnalyticsPrincipal(Base):
    __tablename__ = "analytics_principals"
    __table_args__ = {
        "schema": "app",
        "comment": "Trusted mapping from a database login to its authorized ERP tenant.",
    }

    db_role: Mapped[str] = mapped_column(String(63), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("app.tenants.id", ondelete="RESTRICT"), index=True
    )


class SeedRun(Base):
    __tablename__ = "seed_runs"
    __table_args__ = {"schema": "app", "comment": "Atomic, versioned demo seed completion records."}

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("app.tenants.id", ondelete="RESTRICT"), primary_key=True
    )
    version: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
