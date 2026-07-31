from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0003"
down_revision: str | None = "20260731_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_details",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("fetch_id", sa.Integer(), sa.ForeignKey("fetches.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description_text", sa.Text()),
        sa.Column("attributes_json", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(length=255)),
        sa.Column("overseas_sale", sa.String(length=120)),
        sa.Column("stock", sa.String(length=255)),
        sa.Column("review_url", sa.String(length=2048)),
        sa.Column("coverage", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_product_details_product_observed",
        "product_details",
        ["product_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_details_product_observed", table_name="product_details")
    op.drop_table("product_details")
