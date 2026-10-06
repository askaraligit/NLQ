"""Add encrypted, user-owned PostgreSQL connection metadata.

Revision ID: 0003_data_connections
Revises: 0002_workspace_identity
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_data_connections"
down_revision: str | None = "0002_workspace_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_connections",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("app.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("encrypted_url", sa.Text(), nullable=False),
        sa.Column("schema_name", sa.String(63), nullable=False, server_default=sa.text("'public'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema="app",
        comment="Encrypted user-owned PostgreSQL sources.",
    )
    op.create_index("ix_data_connections_user_id", "data_connections", ["user_id"], schema="app")
    op.execute(
        "CREATE TRIGGER touch_updated_at BEFORE UPDATE ON app.data_connections "
        "FOR EACH ROW EXECUTE FUNCTION erp.touch_updated_at()"
    )
    op.execute("REVOKE ALL ON app.data_connections FROM PUBLIC, nlq_reader")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.data_connections TO nlq_app")


def downgrade() -> None:
    op.execute("REVOKE ALL ON app.data_connections FROM nlq_app")
    op.drop_index("ix_data_connections_user_id", table_name="data_connections", schema="app")
    op.drop_table("data_connections", schema="app")
