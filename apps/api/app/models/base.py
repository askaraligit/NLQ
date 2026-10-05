"""Shared declarative metadata. Importing models never opens a database connection."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, FetchedValue, ForeignKey, MetaData, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=FetchedValue(),
    )


class TenantRecord(Timestamps, Base):
    __abstract__ = True

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("app.tenants.id", ondelete="RESTRICT"),
        comment="Organization owning this record; enforced by foreign keys and reader RLS.",
    )
