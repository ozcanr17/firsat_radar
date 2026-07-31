import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0010"
down_revision: str | None = "20260731_0009"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("marketplace", sa.String(length=120), nullable=True))
    op.add_column("offers", sa.Column("price", sa.Numeric(14, 2), nullable=True))
    op.add_column("offers", sa.Column("currency", sa.String(length=8), nullable=True))
    op.add_column("offers", sa.Column("availability", sa.String(length=40), nullable=True))
    op.add_column("offers", sa.Column("offer_url", sa.String(length=2048), nullable=True))
    op.add_column("offers", sa.Column("stock_text", sa.String(length=255), nullable=True))
    op.add_column("product_snapshots", sa.Column("seller_count", sa.Integer(), nullable=True))
    op.create_index("ix_offers_product_observed", "offers", ["product_id", "observed_at"])


def downgrade() -> None:
    op.drop_index("ix_offers_product_observed", table_name="offers")
    op.drop_column("product_snapshots", "seller_count")
    op.drop_column("offers", "stock_text")
    op.drop_column("offers", "offer_url")
    op.drop_column("offers", "availability")
    op.drop_column("offers", "currency")
    op.drop_column("offers", "price")
    op.drop_column("offers", "marketplace")
