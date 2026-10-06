"""Align workspace table comments with application metadata.

Revision ID: 0004_workspace_table_comments
Revises: 0003_data_connections
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_workspace_table_comments"
down_revision: str | None = "0003_data_connections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COMMENTS = {
    "users": "NLQ users with Argon2 password hashes.",
    "conversations": "User-owned NLQ conversations.",
    "query_records": "Persisted NLQ question, response, and result snapshot.",
    "saved_queries": "Named, user-owned NLQ query snapshots.",
    "user_settings": "One row of persisted workspace preferences per user.",
}


def upgrade() -> None:
    for table, comment in COMMENTS.items():
        op.execute(f"COMMENT ON TABLE app.{table} IS '{comment}'")


def downgrade() -> None:
    for table in COMMENTS:
        op.execute(f"COMMENT ON TABLE app.{table} IS NULL")
