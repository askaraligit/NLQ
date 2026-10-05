"""Provisioning metadata, intentionally inaccessible to analytics readers."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, text
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


class User(Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "app", "comment": "NLQ users with Argon2 password hashes."}

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("app.tenants.id", ondelete="RESTRICT"), index=True
    )
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Conversation(Timestamps, Base):
    __tablename__ = "conversations"
    __table_args__ = {"schema": "app", "comment": "User-owned NLQ conversations."}

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app.users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(180))


class QueryRecord(Base):
    __tablename__ = "query_records"
    __table_args__ = {
        "schema": "app",
        "comment": "Persisted NLQ question, response, and result snapshot.",
    }

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app.users.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("app.conversations.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    sql: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    columns: Mapped[list[dict[str, str]]] = mapped_column(JSON)
    rows: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    visualization: Mapped[dict[str, object]] = mapped_column(JSON)
    execution_time_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class SavedQuery(Timestamps, Base):
    __tablename__ = "saved_queries"
    __table_args__ = {"schema": "app", "comment": "Named, user-owned NLQ query snapshots."}

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app.users.id", ondelete="CASCADE"), index=True
    )
    query_record_id: Mapped[UUID] = mapped_column(
        ForeignKey("app.query_records.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(120))
    question: Mapped[str] = mapped_column(Text)
    sql: Mapped[str] = mapped_column(Text)
    visualization: Mapped[dict[str, object]] = mapped_column(JSON)


class UserSettings(Timestamps, Base):
    __tablename__ = "user_settings"
    __table_args__ = {
        "schema": "app",
        "comment": "One row of persisted workspace preferences per user.",
    }

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app.users.id", ondelete="CASCADE"), primary_key=True
    )
    preferred_page_size: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("25")
    )
    compact_tables: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
