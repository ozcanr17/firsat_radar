from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0008"
down_revision: str | None = "20260731_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watch_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")),
        sa.Column("target_type", sa.String(length=30), nullable=False),
        sa.Column("label", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.String(length=2048), unique=True),
        sa.Column("category", sa.String(length=500)),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("refresh_interval_hours", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "business_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("purchase_cost", sa.Numeric(14, 2)),
        sa.Column("commission_rate", sa.Float(), nullable=False),
        sa.Column("shipping_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("packaging_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("advertising_rate", sa.Float(), nullable=False),
        sa.Column("return_rate", sa.Float(), nullable=False),
        sa.Column("tax_rate", sa.Float(), nullable=False),
        sa.Column("other_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("target_margin_rate", sa.Float(), nullable=False),
        sa.Column("monthly_units", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("product_id"),
    )


def downgrade() -> None:
    op.drop_table("business_cases")
    op.drop_table("watch_targets")
