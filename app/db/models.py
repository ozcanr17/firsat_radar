from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    robots_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_state: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    counts_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))


class CategoryCursor(Base):
    __tablename__ = "category_cursors"
    __table_args__ = (UniqueConstraint("source_id", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    next_page: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    page_size: Mapped[int | None] = mapped_column(Integer)
    pages_scanned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sweeps_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_signature: Mapped[str | None] = mapped_column(String(64))
    last_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Fetch(Base):
    __tablename__ = "fetches"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    status_code: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    coverage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    debug_metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("source_id", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(160), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(500))
    image_url: Mapped[str | None] = mapped_column(String(2048))
    last_fetch_id: Mapped[int | None] = mapped_column(ForeignKey("fetches.id"))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ProductSnapshot(Base):
    __tablename__ = "product_snapshots"
    __table_args__ = (Index("ix_product_snapshots_product_observed", "product_id", "observed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    fetch_id: Mapped[int] = mapped_column(ForeignKey("fetches.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    rating: Mapped[float | None] = mapped_column(Float)
    review_count: Mapped[int | None] = mapped_column(Integer)
    rank: Mapped[int | None] = mapped_column(Integer)
    stock: Mapped[str | None] = mapped_column(String(120))
    coverage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class ProductDetail(Base):
    __tablename__ = "product_details"
    __table_args__ = (Index("ix_product_details_product_observed", "product_id", "observed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    fetch_id: Mapped[int] = mapped_column(ForeignKey("fetches.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    description_text: Mapped[str | None] = mapped_column(Text)
    attributes_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    origin: Mapped[str | None] = mapped_column(String(255))
    overseas_sale: Mapped[str | None] = mapped_column(String(120))
    stock: Mapped[str | None] = mapped_column(String(255))
    review_url: Mapped[str | None] = mapped_column(String(2048))
    coverage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reason_codes_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    fetch_id: Mapped[int] = mapped_column(ForeignKey("fetches.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    seller: Mapped[str | None] = mapped_column(String(500))
    shipping_origin: Mapped[str | None] = mapped_column(String(255))
    delivery_text: Mapped[str | None] = mapped_column(String(1000))


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("product_id", "source_review_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    fetch_id: Mapped[int] = mapped_column(ForeignKey("fetches.id"), nullable=False)
    source_review_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rating: Mapped[float | None] = mapped_column(Float)
    review_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    text_redacted: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ReviewLabel(Base):
    __tablename__ = "review_labels"
    __table_args__ = (UniqueConstraint("review_id", "topic"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"), nullable=False)
    topic: Mapped[str] = mapped_column(String(80), nullable=False)
    polarity: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_span: Mapped[str] = mapped_column(Text, nullable=False)


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (UniqueConstraint("product_id", "fetch_id", "model_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    fetch_id: Mapped[int] = mapped_column(ForeignKey("fetches.id"), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    demand: Mapped[float | None] = mapped_column(Float)
    satisfaction: Mapped[float | None] = mapped_column(Float)
    pain: Mapped[float | None] = mapped_column(Float)
    momentum: Mapped[float | None] = mapped_column(Float)
    price_position: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    coverage: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (UniqueConstraint("analysis_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    pattern: Mapped[str | None] = mapped_column(String(80))
    reasons_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    risks_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    hypothesis_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class RuntimeState(Base):
    __tablename__ = "runtime_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    scheduler_status: Mapped[str] = mapped_column(String(40), default="idle", nullable=False)
    last_job_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_job_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(120))
    last_backup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_retention_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class WatchTarget(Base):
    __tablename__ = "watch_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), unique=True)
    category: Mapped[str | None] = mapped_column(String(500))
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    refresh_interval_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class BusinessCase(Base):
    __tablename__ = "business_cases"
    __table_args__ = (UniqueConstraint("product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    purchase_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    commission_rate: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    packaging_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    advertising_rate: Mapped[float] = mapped_column(Float, default=0.03, nullable=False)
    return_rate: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    other_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    target_margin_rate: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    monthly_units: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
