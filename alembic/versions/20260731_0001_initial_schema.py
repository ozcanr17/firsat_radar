from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("robots_checked_at", sa.DateTime(timezone=True)),
        sa.Column("policy_state", sa.String(length=40), nullable=False),
    )
    op.create_table(
        "crawl_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("counts_json", sa.Text(), nullable=False),
        sa.Column("error_code", sa.String(length=80)),
    )
    op.create_table(
        "fetches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("crawl_runs.id"), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status_code", sa.Integer()),
        sa.Column("content_hash", sa.String(length=64)),
        sa.Column("parser_version", sa.String(length=40), nullable=False),
        sa.Column("coverage", sa.Float(), nullable=False),
        sa.Column("debug_metadata_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_fetches_content_hash", "fetches", ["content_hash"])
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("external_id", sa.String(length=160), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("brand", sa.String(length=255)),
        sa.Column("category", sa.String(length=500)),
        sa.Column("last_fetch_id", sa.Integer(), sa.ForeignKey("fetches.id")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "external_id"),
    )
    op.create_table(
        "product_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("fetch_id", sa.Integer(), sa.ForeignKey("fetches.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(14, 2)),
        sa.Column("old_price", sa.Numeric(14, 2)),
        sa.Column("rating", sa.Float()),
        sa.Column("review_count", sa.Integer()),
        sa.Column("rank", sa.Integer()),
        sa.Column("stock", sa.String(length=120)),
        sa.Column("coverage", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
    )
    op.create_index(
        "ix_product_snapshots_product_observed",
        "product_snapshots",
        ["product_id", "observed_at"],
    )
    op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("fetch_id", sa.Integer(), sa.ForeignKey("fetches.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seller", sa.String(length=500)),
        sa.Column("shipping_origin", sa.String(length=255)),
        sa.Column("delivery_text", sa.String(length=1000)),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("fetch_id", sa.Integer(), sa.ForeignKey("fetches.id"), nullable=False),
        sa.Column("source_review_id", sa.String(length=64), nullable=False),
        sa.Column("rating", sa.Float()),
        sa.Column("review_date", sa.DateTime(timezone=True)),
        sa.Column("text_redacted", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("product_id", "source_review_id"),
    )
    op.create_table(
        "review_labels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("topic", sa.String(length=80), nullable=False),
        sa.Column("polarity", sa.String(length=20), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_span", sa.Text(), nullable=False),
    )
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("fetch_id", sa.Integer(), sa.ForeignKey("fetches.id"), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("demand", sa.Float()),
        sa.Column("satisfaction", sa.Float()),
        sa.Column("pain", sa.Float()),
        sa.Column("momentum", sa.Float()),
        sa.Column("price_position", sa.Float()),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("coverage", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
    )
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("pattern", sa.String(length=80)),
        sa.Column("reasons_json", sa.Text(), nullable=False),
        sa.Column("risks_json", sa.Text(), nullable=False),
        sa.Column("hypothesis_json", sa.Text(), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
    )
    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=120), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_table("opportunities")
    op.drop_table("analyses")
    op.drop_table("review_labels")
    op.drop_table("reviews")
    op.drop_table("offers")
    op.drop_index("ix_product_snapshots_product_observed", table_name="product_snapshots")
    op.drop_table("product_snapshots")
    op.drop_table("products")
    op.drop_index("ix_fetches_content_hash", table_name="fetches")
    op.drop_table("fetches")
    op.drop_table("crawl_runs")
    op.drop_table("sources")
