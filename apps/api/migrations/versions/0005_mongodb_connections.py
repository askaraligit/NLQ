"""Add MongoDB source metadata and query language history.

Revision ID: 0005_mongodb_connections
Revises: 0004_workspace_table_comments
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_mongodb_connections"
down_revision: str | None = "0004_workspace_table_comments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "data_connections",
        sa.Column("source_type", sa.String(16), nullable=False, server_default=sa.text("'postgresql'")),
        schema="app",
    )
    op.add_column(
        "data_connections", sa.Column("database_name", sa.String(128), nullable=True), schema="app"
    )
    op.create_check_constraint(
        "ck_data_connections_source_type",
        "data_connections",
        "source_type IN ('postgresql', 'mongodb')",
        schema="app",
    )
    op.execute("COMMENT ON TABLE app.data_connections IS 'Encrypted user-owned database sources.'")
    op.add_column(
        "query_records",
        sa.Column("query_language", sa.String(16), nullable=False, server_default=sa.text("'sql'")),
        schema="app",
    )
    op.create_check_constraint(
        "ck_query_records_query_language",
        "query_records",
        "query_language IN ('sql', 'mongodb')",
        schema="app",
    )


def downgrade() -> None:
    op.drop_constraint("ck_query_records_query_language", "query_records", schema="app")
    op.drop_column("query_records", "query_language", schema="app")
    op.drop_constraint("ck_data_connections_source_type", "data_connections", schema="app")
    op.drop_column("data_connections", "database_name", schema="app")
    op.drop_column("data_connections", "source_type", schema="app")
    op.execute("COMMENT ON TABLE app.data_connections IS 'Encrypted user-owned PostgreSQL sources.'")
