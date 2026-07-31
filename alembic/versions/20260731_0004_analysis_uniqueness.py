from collections.abc import Sequence

from alembic import op

revision: str = "20260731_0004"
down_revision: str | None = "20260731_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_review_labels_review_topic",
        "review_labels",
        ["review_id", "topic"],
        unique=True,
    )
    op.create_index(
        "uq_analyses_product_fetch_model",
        "analyses",
        ["product_id", "fetch_id", "model_version"],
        unique=True,
    )
    op.create_index(
        "uq_opportunities_analysis",
        "opportunities",
        ["analysis_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_opportunities_analysis", table_name="opportunities")
    op.drop_index("uq_analyses_product_fetch_model", table_name="analyses")
    op.drop_index("uq_review_labels_review_topic", table_name="review_labels")
