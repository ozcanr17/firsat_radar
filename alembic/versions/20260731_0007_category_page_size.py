from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0007"
down_revision: str | None = "20260731_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("category_cursors", sa.Column("page_size", sa.Integer()))


def downgrade() -> None:
    op.drop_column("category_cursors", "page_size")
