"""Add user-scoped identity, conversations, history, and saved query records.

Revision ID: 0002_workspace_identity
Revises: 0001_erp_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_workspace_identity"
down_revision: str | None = "0001_erp_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKSPACE_TABLES = ("users", "conversations", "query_records", "saved_queries", "user_settings")


def _timestamps(table: str) -> None:
    op.execute(
        f"CREATE TRIGGER touch_updated_at BEFORE UPDATE ON app.{table} "
        "FOR EACH ROW EXECUTE FUNCTION erp.touch_updated_at()"
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("app.tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema="app",
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"], schema="app")
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("app.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema="app",
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"], schema="app")
    op.create_table(
        "query_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("app.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("app.conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("visualization", sa.JSON(), nullable=False),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema="app",
    )
    op.create_index("ix_query_records_user_id", "query_records", ["user_id"], schema="app")
    op.create_index("ix_query_records_conversation_id", "query_records", ["conversation_id"], schema="app")
    op.create_table(
        "saved_queries",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("app.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_record_id", sa.Uuid(), sa.ForeignKey("app.query_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("visualization", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema="app",
    )
    op.create_index("ix_saved_queries_user_id", "saved_queries", ["user_id"], schema="app")
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("app.users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("preferred_page_size", sa.Integer(), nullable=False, server_default=sa.text("25")),
        sa.Column("compact_tables", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("preferred_page_size IN (10, 25, 50, 100)", name="valid_page_size"),
        schema="app",
    )
    for table in ("users", "conversations", "saved_queries", "user_settings"):
        _timestamps(table)
    for table in WORKSPACE_TABLES:
        op.execute(f"REVOKE ALL ON app.{table} FROM PUBLIC, nlq_reader")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON app.{table} TO nlq_app")


def downgrade() -> None:
    for table in WORKSPACE_TABLES:
        op.execute(f"REVOKE ALL ON app.{table} FROM nlq_app")
    op.drop_table("user_settings", schema="app")
    op.drop_index("ix_saved_queries_user_id", table_name="saved_queries", schema="app")
    op.drop_table("saved_queries", schema="app")
    op.drop_index("ix_query_records_conversation_id", table_name="query_records", schema="app")
    op.drop_index("ix_query_records_user_id", table_name="query_records", schema="app")
    op.drop_table("query_records", schema="app")
    op.drop_index("ix_conversations_user_id", table_name="conversations", schema="app")
    op.drop_table("conversations", schema="app")
    op.drop_index("ix_users_tenant_id", table_name="users", schema="app")
    op.drop_table("users", schema="app")
