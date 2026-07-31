from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select

from app.db.models import BusinessCase, Product, WatchTarget
from app.db.session import SessionFactory
from app.services.products import ProductView, list_latest_products

MONEY = Decimal("0.01")
ALLOWED_TARGET_TYPES = {"product", "category"}


@dataclass(frozen=True)
class WatchTargetInput:
    target_type: str
    label: str
    source_url: str | None
    category: str | None
    priority: int
    refresh_interval_hours: int


@dataclass(frozen=True)
class WatchTargetView:
    id: int
    product_id: int | None
    target_type: str
    label: str
    source_url: str | None
    category: str | None
    priority: int
    refresh_interval_hours: int
    enabled: bool
    last_checked_at: datetime | None
    last_status: str
    freshness_hours: float | None
    refresh_due: bool
    queue_score: float


@dataclass(frozen=True)
class BusinessCaseInput:
    purchase_cost: Decimal | None
    commission_rate: float
    shipping_cost: Decimal
    packaging_cost: Decimal
    advertising_rate: float
    return_rate: float
    tax_rate: float
    other_cost: Decimal
    target_margin_rate: float
    monthly_units: int
    notes: str | None


@dataclass(frozen=True)
class UnitEconomics:
    sale_price: Decimal | None
    variable_cost: Decimal | None
    contribution: Decimal | None
    margin_rate: float | None
    return_on_cost: float | None
    break_even_price: Decimal | None
    target_sale_price: Decimal | None
    monthly_contribution: Decimal | None
    decision: str


@dataclass(frozen=True)
class BusinessCaseView:
    product_id: int
    title: str
    source_url: str
    case: BusinessCaseInput
    economics: UnitEconomics
    updated_at: datetime


def normalize_hepsiburada_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or hostname not in {"hepsiburada.com", "www.hepsiburada.com"}:
        raise ValueError("invalid_hepsiburada_url")
    if not parsed.path.startswith("/") or parsed.path.startswith("/product-comment/"):
        raise ValueError("forbidden_target_url")
    return urlunsplit(("https", "www.hepsiburada.com", parsed.path.rstrip("/"), "", ""))


def add_watch_target(
    session_factory: SessionFactory,
    target: WatchTargetInput,
) -> WatchTargetView:
    target_type = target.target_type.strip().casefold()
    if target_type not in ALLOWED_TARGET_TYPES:
        raise ValueError("invalid_target_type")
    label = target.label.strip()
    if not label:
        raise ValueError("label_required")
    if not 1 <= target.priority <= 5:
        raise ValueError("invalid_priority")
    if not 1 <= target.refresh_interval_hours <= 168:
        raise ValueError("invalid_refresh_interval")
    source_url = normalize_hepsiburada_url(target.source_url) if target.source_url else None
    if target_type == "product" and source_url is None:
        raise ValueError("product_url_required")
    category = target.category.strip() if target.category else None
    with session_factory.begin() as session:
        product = (
            session.scalar(select(Product).where(Product.canonical_url == source_url))
            if source_url
            else None
        )
        watch_target = (
            session.scalar(select(WatchTarget).where(WatchTarget.source_url == source_url))
            if source_url
            else None
        )
        if watch_target is None:
            watch_target = WatchTarget(
                product_id=product.id if product else None,
                target_type=target_type,
                label=label,
                source_url=source_url,
                category=category,
                priority=target.priority,
                refresh_interval_hours=target.refresh_interval_hours,
            )
            session.add(watch_target)
            session.flush()
        else:
            watch_target.product_id = product.id if product else watch_target.product_id
            watch_target.target_type = target_type
            watch_target.label = label
            watch_target.category = category
            watch_target.priority = target.priority
            watch_target.refresh_interval_hours = target.refresh_interval_hours
            watch_target.enabled = True
        target_id = watch_target.id
    return next(item for item in list_watch_targets(session_factory) if item.id == target_id)


def remove_watch_target(session_factory: SessionFactory, target_id: int) -> bool:
    with session_factory.begin() as session:
        target = session.get(WatchTarget, target_id)
        if target is None:
            return False
        session.delete(target)
    return True


def list_watch_targets(
    session_factory: SessionFactory,
    now: datetime | None = None,
) -> list[WatchTargetView]:
    current = now or datetime.now(UTC)
    products = {product.id: product for product in list_latest_products(session_factory, 500)}
    with session_factory() as session:
        targets = session.scalars(
            select(WatchTarget).order_by(WatchTarget.priority.desc(), WatchTarget.created_at)
        ).all()
    views = [
        watch_target_view(
            target,
            products.get(target.product_id) if target.product_id is not None else None,
            current,
        )
        for target in targets
    ]
    return sorted(views, key=lambda item: (-item.queue_score, item.label.casefold()))


def watch_target_view(
    target: WatchTarget,
    product: ProductView | None,
    now: datetime,
) -> WatchTargetView:
    reference = target.last_checked_at or (product.observed_at if product else None)
    freshness_hours = hours_since(reference, now) if reference else None
    refresh_due = freshness_hours is None or freshness_hours >= target.refresh_interval_hours
    opportunity = product.opportunity_score if product and product.opportunity_score else 0.0
    age_signal = min(freshness_hours or 168.0, 168.0) / 8.4
    unresolved_signal = 25.0 if target.product_id is None else 0.0
    queue_score = round(
        target.priority * 12.0 + age_signal + opportunity * 0.2 + unresolved_signal, 1
    )
    return WatchTargetView(
        id=target.id,
        product_id=target.product_id,
        target_type=target.target_type,
        label=target.label,
        source_url=target.source_url,
        category=target.category,
        priority=target.priority,
        refresh_interval_hours=target.refresh_interval_hours,
        enabled=target.enabled,
        last_checked_at=target.last_checked_at,
        last_status=target.last_status,
        freshness_hours=round(freshness_hours, 1) if freshness_hours is not None else None,
        refresh_due=refresh_due,
        queue_score=queue_score,
    )


def save_business_case(
    session_factory: SessionFactory,
    product_id: int,
    values: BusinessCaseInput,
) -> BusinessCaseView:
    validate_business_case(values)
    with session_factory.begin() as session:
        product = session.get(Product, product_id)
        if product is None:
            raise ValueError("product_not_found")
        business_case = session.scalar(
            select(BusinessCase).where(BusinessCase.product_id == product_id)
        )
        if business_case is None:
            business_case = BusinessCase(product_id=product_id)
            session.add(business_case)
        business_case.purchase_cost = values.purchase_cost
        business_case.commission_rate = values.commission_rate
        business_case.shipping_cost = values.shipping_cost
        business_case.packaging_cost = values.packaging_cost
        business_case.advertising_rate = values.advertising_rate
        business_case.return_rate = values.return_rate
        business_case.tax_rate = values.tax_rate
        business_case.other_cost = values.other_cost
        business_case.target_margin_rate = values.target_margin_rate
        business_case.monthly_units = values.monthly_units
        business_case.notes = values.notes.strip() if values.notes else None
    result = get_business_case(session_factory, product_id)
    if result is None:
        raise RuntimeError("business_case_persistence_failed")
    return result


def get_business_case(
    session_factory: SessionFactory,
    product_id: int,
) -> BusinessCaseView | None:
    products = {product.id: product for product in list_latest_products(session_factory, 500)}
    product = products.get(product_id)
    if product is None:
        return None
    with session_factory() as session:
        business_case = session.scalar(
            select(BusinessCase).where(BusinessCase.product_id == product_id)
        )
        if business_case is None:
            return None
        values = business_case_input(business_case)
        updated_at = business_case.updated_at
    return BusinessCaseView(
        product_id=product_id,
        title=product.title,
        source_url=product.source_url,
        case=values,
        economics=calculate_unit_economics(product.price, values),
        updated_at=updated_at,
    )


def list_business_cases(session_factory: SessionFactory) -> list[BusinessCaseView]:
    with session_factory() as session:
        product_ids = session.scalars(select(BusinessCase.product_id)).all()
    return [
        item
        for product_id in product_ids
        if (item := get_business_case(session_factory, product_id)) is not None
    ]


def calculate_unit_economics(
    sale_price: Decimal | None,
    values: BusinessCaseInput,
) -> UnitEconomics:
    if values.purchase_cost is None:
        return UnitEconomics(sale_price, None, None, None, None, None, None, None, "incomplete")
    rate_total = Decimal(
        str(values.commission_rate + values.advertising_rate + values.return_rate + values.tax_rate)
    )
    fixed_cost = (
        values.purchase_cost + values.shipping_cost + values.packaging_cost + values.other_cost
    )
    break_even_denominator = Decimal("1") - rate_total
    break_even = (
        money(fixed_cost / break_even_denominator)
        if break_even_denominator > Decimal("0")
        else None
    )
    target_denominator = break_even_denominator - Decimal(str(values.target_margin_rate))
    target_price = money(fixed_cost / target_denominator) if target_denominator > 0 else None
    if sale_price is None or sale_price <= 0:
        return UnitEconomics(
            sale_price,
            None,
            None,
            None,
            None,
            break_even,
            target_price,
            None,
            "price_missing",
        )
    percentage_cost = sale_price * rate_total
    variable_cost = money(fixed_cost + percentage_cost)
    contribution = money(sale_price - variable_cost)
    margin_rate = float(contribution / sale_price)
    return_on_cost = float(contribution / fixed_cost) if fixed_cost > 0 else None
    monthly_contribution = money(contribution * values.monthly_units)
    decision = "go" if margin_rate >= values.target_margin_rate and contribution > 0 else "no_go"
    return UnitEconomics(
        sale_price=money(sale_price),
        variable_cost=variable_cost,
        contribution=contribution,
        margin_rate=round(margin_rate, 4),
        return_on_cost=round(return_on_cost, 4) if return_on_cost is not None else None,
        break_even_price=break_even,
        target_sale_price=target_price,
        monthly_contribution=monthly_contribution,
        decision=decision,
    )


def validate_business_case(values: BusinessCaseInput) -> None:
    money_values = (
        values.purchase_cost,
        values.shipping_cost,
        values.packaging_cost,
        values.other_cost,
    )
    if any(value is not None and value < 0 for value in money_values):
        raise ValueError("negative_cost")
    rates = (
        values.commission_rate,
        values.advertising_rate,
        values.return_rate,
        values.tax_rate,
        values.target_margin_rate,
    )
    if any(rate < 0 or rate >= 1 for rate in rates):
        raise ValueError("invalid_rate")
    if values.monthly_units < 0:
        raise ValueError("invalid_monthly_units")


def business_case_input(value: BusinessCase) -> BusinessCaseInput:
    return BusinessCaseInput(
        purchase_cost=value.purchase_cost,
        commission_rate=value.commission_rate,
        shipping_cost=value.shipping_cost,
        packaging_cost=value.packaging_cost,
        advertising_rate=value.advertising_rate,
        return_rate=value.return_rate,
        tax_rate=value.tax_rate,
        other_cost=value.other_cost,
        target_margin_rate=value.target_margin_rate,
        monthly_units=value.monthly_units,
        notes=value.notes,
    )


def hours_since(value: datetime, now: datetime) -> float:
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    current = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
    return max((current - aware).total_seconds() / 3600.0, 0.0)


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)
