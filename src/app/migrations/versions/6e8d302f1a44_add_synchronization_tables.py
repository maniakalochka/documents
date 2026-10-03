"""Track completed CSV imports and pending Elasticsearch deletions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6e8d302f1a44"
down_revision: str | Sequence[str] | None = "0fa998dcfe89"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("checksum", sa.String(64), primary_key=True),
        sa.Column("created_date", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "pending_index_deletions",
        sa.Column("document_id", sa.Integer(), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("pending_index_deletions")
    op.drop_table("import_batches")
