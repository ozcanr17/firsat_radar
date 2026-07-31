import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import (
    CrawlRun,
    Fetch,
    Offer,
    Product,
    ProductDetail,
    ProductSnapshot,
    Review,
    Source,
    WatchTarget,
)
from app.db.session import SessionFactory
from app.domain.crawl import (
    CrawlLimits,
    CrawlSummary,
    FetchedDocument,
    ListingResult,
    ParserDriftError,
    PolicyDecision,
    PolicyState,
    ProductDetailResult,
    ProductStub,
    RunStatus,
    SourceAccessError,
)
from app.services.raw_store import RawStore
from app.sources.base import SourceAdapter
from app.sources.hepsiburada.parser import extract_external_id

AdapterFactory = Callable[[], SourceAdapter]


class CrawlService:
    def __init__(
        self,
        settings: Settings,
        session_factory: SessionFactory,
        adapter_factory: AdapterFactory,
        *,
        source_name: str = "hepsiburada",
        source_base_url: str = "https://www.hepsiburada.com",
        robots_url: str = "https://www.hepsiburada.com/robots.txt",
        start_url: str | None = None,
        start_category: str = "Anne / Bebek / Oyuncak",
        external_id_extractor: Callable[[str], str | None] = extract_external_id,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.adapter_factory = adapter_factory
        self.raw_store = RawStore(settings.data_dir / "raw")
        self.source_name = source_name
        self.source_base_url = source_base_url
        self.robots_url = robots_url
        self.start_url = start_url or settings.hepsiburada_start_url
        self.start_category = start_category
        self.external_id_extractor = external_id_extractor

    async def policy_check(self, target_url: str | None = None) -> PolicyDecision:
        url = target_url or self.start_url
        async with self.adapter_factory() as adapter:
            decision = await adapter.policy_check(url)
        with self.session_factory.begin() as session:
            source = self._get_or_create_source(session)
            source.robots_checked_at = decision.checked_at
            source.policy_state = decision.state.value
        return decision

    async def crawl(self, limits: CrawlLimits) -> CrawlSummary:
        return await self.crawl_target(
            self.start_url,
            self.start_category,
            limits,
        )

    async def crawl_target(
        self,
        target_url: str,
        category_name: str,
        limits: CrawlLimits,
    ) -> CrawlSummary:
        limits.validate()
        run_id = self._start_run()
        try:
            async with self.adapter_factory() as adapter:
                decision = await adapter.policy_check(target_url)
                self._record_policy(run_id, decision)
                if not decision.allowed:
                    return self._finish_for_policy(run_id, decision)
                listing = await adapter.discover(target_url, limits)
                detail_results = []
                for product in listing.products[: limits.details]:
                    detail_results.append(await adapter.enrich(product))
                details = tuple(detail_results)
            return self._persist_crawl(run_id, listing, details, category_name)
        except SourceAccessError as error:
            return self._finish_with_error(run_id, error.status, error.error_code)
        except ParserDriftError as error:
            return self._finish_with_error(run_id, RunStatus.PARSER_DRIFT, str(error))
        except Exception:
            self._finish_with_error(run_id, RunStatus.FAILED, "unexpected_error")
            raise

    async def refresh_product(self, product_id: int) -> CrawlSummary:
        with self.session_factory() as session:
            product = session.get(Product, product_id)
            if product is None:
                raise ValueError("product_not_found")
            snapshot = session.scalar(
                select(ProductSnapshot)
                .where(ProductSnapshot.product_id == product_id)
                .order_by(ProductSnapshot.observed_at.desc(), ProductSnapshot.id.desc())
                .limit(1)
            )
            stub = ProductStub(
                external_id=product.external_id,
                source_url=product.canonical_url,
                title=product.title,
                price=snapshot.price if snapshot else None,
                old_price=snapshot.old_price if snapshot else None,
                rating=snapshot.rating if snapshot else None,
                review_count=snapshot.review_count if snapshot else None,
                rank=snapshot.rank if snapshot and snapshot.rank is not None else 1,
                image_url=product.image_url,
                delivery_text=None,
                coverage=snapshot.coverage if snapshot else 0.0,
                confidence=snapshot.confidence if snapshot else 0.0,
            )
        run_id = self._start_run()
        try:
            async with self.adapter_factory() as adapter:
                decision = await adapter.policy_check(stub.source_url)
                self._record_policy(run_id, decision)
                if not decision.allowed:
                    return self._finish_for_policy(run_id, decision)
                detail = await adapter.enrich(stub)
            return self._persist_product_refresh(run_id, product_id, detail, stub)
        except SourceAccessError as error:
            return self._finish_with_error(run_id, error.status, error.error_code)
        except ParserDriftError as error:
            return self._finish_with_error(run_id, RunStatus.PARSER_DRIFT, str(error))
        except Exception:
            self._finish_with_error(run_id, RunStatus.FAILED, "unexpected_error")
            raise

    async def discover_product(
        self,
        source_url: str,
        label: str,
        category: str | None,
    ) -> CrawlSummary:
        external_id = self.external_id_extractor(source_url)
        if external_id is None:
            raise ValueError("invalid_product_url")
        with self.session_factory() as session:
            source = session.scalar(select(Source).where(Source.name == self.source_name))
            product = (
                session.scalar(
                    select(Product).where(
                        Product.source_id == source.id,
                        Product.external_id == external_id,
                    )
                )
                if source is not None
                else None
            )
        if product is not None:
            return await self.refresh_product(product.id)
        stub = ProductStub(
            external_id=external_id,
            source_url=source_url,
            title=label,
            price=None,
            old_price=None,
            rating=None,
            review_count=None,
            rank=1,
            image_url=None,
            delivery_text=None,
            coverage=0.5,
            confidence=0.5,
        )
        run_id = self._start_run()
        try:
            async with self.adapter_factory() as adapter:
                decision = await adapter.policy_check(source_url)
                self._record_policy(run_id, decision)
                if not decision.allowed:
                    return self._finish_for_policy(run_id, decision)
                detail = await adapter.enrich(stub)
            return self._persist_product_discovery(run_id, stub, detail, category)
        except SourceAccessError as error:
            return self._finish_with_error(run_id, error.status, error.error_code)
        except ParserDriftError as error:
            return self._finish_with_error(run_id, RunStatus.PARSER_DRIFT, str(error))
        except Exception:
            self._finish_with_error(run_id, RunStatus.FAILED, "unexpected_error")
            raise

    def _start_run(self) -> int:
        with self.session_factory.begin() as session:
            source = self._get_or_create_source(session)
            run = CrawlRun(
                source_id=source.id,
                status=RunStatus.RUNNING.value,
                counts_json="{}",
            )
            session.add(run)
            session.flush()
            return run.id

    def _record_policy(self, run_id: int, decision: PolicyDecision) -> None:
        raw_path = self.raw_store.save(
            decision.content,
            decision.content_hash,
            decision.checked_at,
            "txt",
        )
        with self.session_factory.begin() as session:
            run = session.get_one(CrawlRun, run_id)
            source = session.get_one(Source, run.source_id)
            source.robots_checked_at = decision.checked_at
            source.policy_state = decision.state.value
            session.add(
                Fetch(
                    run_id=run_id,
                    url=self.robots_url,
                    fetched_at=decision.checked_at,
                    status_code=decision.status_code,
                    content_hash=decision.content_hash,
                    parser_version="robots-v1",
                    coverage=1.0 if decision.content else 0.0,
                    debug_metadata_json=json.dumps(
                        {
                            "cached": decision.cached,
                            "raw_path": str(raw_path),
                            "target_url": decision.url,
                        }
                    ),
                )
            )

    def _persist_crawl(
        self,
        run_id: int,
        listing: ListingResult,
        details: tuple[ProductDetailResult, ...],
        category_name: str,
    ) -> CrawlSummary:
        raw_path = self.raw_store.save(
            listing.raw_html,
            listing.content_hash,
            listing.fetched_at,
            "html",
        )
        with self.session_factory.begin() as session:
            duplicate = session.scalar(
                select(Fetch.id).where(
                    Fetch.url == listing.url,
                    Fetch.content_hash == listing.content_hash,
                    Fetch.status_code == listing.status_code,
                )
            )
            fetch = Fetch(
                run_id=run_id,
                url=listing.url,
                fetched_at=listing.fetched_at,
                status_code=listing.status_code,
                content_hash=listing.content_hash,
                parser_version=listing.parser_version,
                coverage=listing.coverage,
                debug_metadata_json=json.dumps(
                    {
                        "candidate_count": listing.candidate_count,
                        "category_link_count": len(listing.category_links),
                        "raw_path": str(raw_path),
                        "selector": "main article",
                    }
                ),
            )
            session.add(fetch)
            session.flush()
            source_id = session.get_one(CrawlRun, run_id).source_id
            self._persist_category_links(session, listing, category_name)
            products_created = 0
            products_updated = 0
            snapshots_created = 0
            products_by_external_id: dict[str, Product] = {}
            for stub in listing.products:
                product = session.scalar(
                    select(Product).where(
                        Product.source_id == source_id,
                        Product.external_id == stub.external_id,
                    )
                )
                if product is None:
                    product = Product(
                        source_id=source_id,
                        external_id=stub.external_id,
                        canonical_url=stub.source_url,
                        title=stub.title,
                        category=category_name,
                        image_url=stub.image_url,
                        last_fetch_id=fetch.id,
                        last_seen_at=listing.fetched_at,
                    )
                    session.add(product)
                    session.flush()
                    products_created += 1
                elif duplicate is None:
                    product.canonical_url = stub.source_url
                    product.title = stub.title
                    product.image_url = stub.image_url
                    product.last_fetch_id = fetch.id
                    product.last_seen_at = listing.fetched_at
                    products_updated += 1
                products_by_external_id[stub.external_id] = product
                if duplicate is None:
                    session.add(
                        ProductSnapshot(
                            product_id=product.id,
                            fetch_id=fetch.id,
                            observed_at=listing.fetched_at,
                            price=stub.price,
                            old_price=stub.old_price,
                            rating=stub.rating,
                            review_count=stub.review_count,
                            rank=stub.rank,
                            coverage=stub.coverage,
                            confidence=stub.confidence,
                        )
                    )
                    snapshots_created += 1
                    if stub.delivery_text:
                        session.add(
                            Offer(
                                product_id=product.id,
                                fetch_id=fetch.id,
                                observed_at=listing.fetched_at,
                                delivery_text=stub.delivery_text,
                            )
                        )
            details_created = 0
            reviews_created = 0
            for detail in details:
                product = products_by_external_id.get(detail.listing_external_id)
                if product is None:
                    continue
                detail_fetch = self._persist_document_fetch(
                    session,
                    run_id,
                    detail.detail_document,
                    {
                        "kind": "product_detail",
                        "reason_codes": detail.reason_codes,
                    },
                )
                product.canonical_url = detail.canonical_url
                product.title = detail.title
                product.brand = detail.brand
                product.last_fetch_id = detail_fetch.id
                product.last_seen_at = detail.detail_document.fetched_at
                session.add(
                    ProductDetail(
                        product_id=product.id,
                        fetch_id=detail_fetch.id,
                        observed_at=detail.detail_document.fetched_at,
                        description_text=detail.description,
                        attributes_json=json.dumps(detail.attributes, ensure_ascii=False),
                        origin=detail.origin,
                        overseas_sale=detail.overseas_sale,
                        stock=detail.stock,
                        review_url=detail.review_url,
                        coverage=detail.coverage,
                        confidence=detail.confidence,
                        reason_codes_json=json.dumps(detail.reason_codes, ensure_ascii=False),
                    )
                )
                details_created += 1
                if detail.seller:
                    session.add(
                        Offer(
                            product_id=product.id,
                            fetch_id=detail_fetch.id,
                            observed_at=detail.detail_document.fetched_at,
                            seller=detail.seller,
                        )
                    )
                if detail.review_document is None:
                    continue
                review_fetch = self._persist_document_fetch(
                    session,
                    run_id,
                    detail.review_document,
                    {
                        "identity_redacted": True,
                        "kind": "public_reviews",
                        "review_count": len(detail.reviews),
                    },
                )
                for review in detail.reviews:
                    existing = session.scalar(
                        select(Review).where(
                            Review.product_id == product.id,
                            Review.source_review_id == review.source_review_id,
                        )
                    )
                    if existing is not None:
                        continue
                    session.add(
                        Review(
                            product_id=product.id,
                            fetch_id=review_fetch.id,
                            source_review_id=review.source_review_id,
                            rating=review.rating,
                            review_date=review.review_date,
                            text_redacted=review.text_redacted,
                            source_url=review.source_url,
                            observed_at=detail.review_document.fetched_at,
                        )
                    )
                    reviews_created += 1
            status = (
                RunStatus.UNCHANGED
                if duplicate is not None and not details
                else RunStatus.COMPLETED
            )
            listing_signature = hashlib.sha256(
                "\n".join(product.external_id for product in listing.products).encode()
            ).hexdigest()
            return self._finish_in_session(
                session,
                run_id,
                status,
                products_seen=len(listing.products),
                products_created=products_created,
                products_updated=products_updated,
                snapshots_created=snapshots_created,
                details_created=details_created,
                reviews_created=reviews_created,
                fetches_created=self._fetch_count(session, run_id),
                listing_signature=listing_signature,
            )

    def _persist_document_fetch(
        self,
        session: Session,
        run_id: int,
        document: FetchedDocument,
        metadata: dict[str, object],
    ) -> Fetch:
        raw_path = self.raw_store.save(
            document.raw_html,
            document.content_hash,
            document.fetched_at,
            "html",
        )
        fetch = Fetch(
            run_id=run_id,
            url=document.url,
            fetched_at=document.fetched_at,
            status_code=document.status_code,
            content_hash=document.content_hash,
            parser_version=document.parser_version,
            coverage=document.coverage,
            debug_metadata_json=json.dumps(
                {**metadata, "confidence": document.confidence, "raw_path": str(raw_path)},
                ensure_ascii=False,
            ),
        )
        session.add(fetch)
        session.flush()
        return fetch

    def _persist_product_refresh(
        self,
        run_id: int,
        product_id: int,
        detail: ProductDetailResult,
        fallback: ProductStub | None = None,
    ) -> CrawlSummary:
        with self.session_factory.begin() as session:
            product = session.get_one(Product, product_id)
            detail_fetch = self._persist_document_fetch(
                session,
                run_id,
                detail.detail_document,
                {"kind": "watchlist_product_detail", "reason_codes": detail.reason_codes},
            )
            product.canonical_url = detail.canonical_url
            product.title = detail.title
            product.brand = detail.brand
            product.image_url = (
                detail.image_url or (fallback.image_url if fallback else None) or product.image_url
            )
            product.last_fetch_id = detail_fetch.id
            product.last_seen_at = detail.detail_document.fetched_at
            session.add(
                ProductSnapshot(
                    product_id=product.id,
                    fetch_id=detail_fetch.id,
                    observed_at=detail.detail_document.fetched_at,
                    price=detail.price
                    if detail.price is not None
                    else fallback.price
                    if fallback
                    else None,
                    old_price=(
                        detail.old_price
                        if detail.old_price is not None
                        else fallback.old_price
                        if fallback
                        else None
                    ),
                    rating=(
                        detail.rating
                        if detail.rating is not None
                        else fallback.rating
                        if fallback
                        else None
                    ),
                    review_count=(
                        detail.review_count
                        if detail.review_count is not None
                        else fallback.review_count
                        if fallback
                        else None
                    ),
                    rank=1,
                    coverage=detail.coverage,
                    confidence=detail.confidence,
                )
            )
            session.add(
                ProductDetail(
                    product_id=product.id,
                    fetch_id=detail_fetch.id,
                    observed_at=detail.detail_document.fetched_at,
                    description_text=detail.description,
                    attributes_json=json.dumps(detail.attributes, ensure_ascii=False),
                    origin=detail.origin,
                    overseas_sale=detail.overseas_sale,
                    stock=detail.stock,
                    review_url=detail.review_url,
                    coverage=detail.coverage,
                    confidence=detail.confidence,
                    reason_codes_json=json.dumps(detail.reason_codes, ensure_ascii=False),
                )
            )
            if detail.seller:
                session.add(
                    Offer(
                        product_id=product.id,
                        fetch_id=detail_fetch.id,
                        observed_at=detail.detail_document.fetched_at,
                        seller=detail.seller,
                    )
                )
            reviews_created = 0
            if detail.review_document is not None:
                review_fetch = self._persist_document_fetch(
                    session,
                    run_id,
                    detail.review_document,
                    {
                        "identity_redacted": True,
                        "kind": "watchlist_public_reviews",
                        "review_count": len(detail.reviews),
                    },
                )
                for review in detail.reviews:
                    existing = session.scalar(
                        select(Review).where(
                            Review.product_id == product.id,
                            Review.source_review_id == review.source_review_id,
                        )
                    )
                    if existing is not None:
                        continue
                    session.add(
                        Review(
                            product_id=product.id,
                            fetch_id=review_fetch.id,
                            source_review_id=review.source_review_id,
                            rating=review.rating,
                            review_date=review.review_date,
                            text_redacted=review.text_redacted,
                            source_url=review.source_url,
                            observed_at=detail.review_document.fetched_at,
                        )
                    )
                    reviews_created += 1
            signature = hashlib.sha256(product.external_id.encode()).hexdigest()
            return self._finish_in_session(
                session,
                run_id,
                RunStatus.COMPLETED,
                products_seen=1,
                products_created=0,
                products_updated=1,
                snapshots_created=1,
                details_created=1,
                reviews_created=reviews_created,
                fetches_created=self._fetch_count(session, run_id),
                listing_signature=signature,
            )

    def _persist_product_discovery(
        self,
        run_id: int,
        stub: ProductStub,
        detail: ProductDetailResult,
        category: str | None,
    ) -> CrawlSummary:
        with self.session_factory.begin() as session:
            source_id = session.get_one(CrawlRun, run_id).source_id
            product = Product(
                source_id=source_id,
                external_id=stub.external_id,
                canonical_url=detail.canonical_url,
                title=detail.title,
                brand=detail.brand,
                category=category,
                image_url=detail.image_url,
                last_seen_at=detail.detail_document.fetched_at,
            )
            session.add(product)
            session.flush()
            product_id = product.id
        summary = self._persist_product_refresh(run_id, product_id, detail, stub)
        return CrawlSummary(
            run_id=summary.run_id,
            status=summary.status,
            products_seen=summary.products_seen,
            products_created=1,
            products_updated=0,
            snapshots_created=summary.snapshots_created,
            details_created=summary.details_created,
            reviews_created=summary.reviews_created,
            fetches_created=summary.fetches_created,
            error_code=summary.error_code,
            listing_signature=summary.listing_signature,
        )

    def _finish_for_policy(self, run_id: int, decision: PolicyDecision) -> CrawlSummary:
        status_by_state = {
            PolicyState.BLOCKED: RunStatus.BLOCKED,
            PolicyState.DENIED: RunStatus.POLICY_DENIED,
            PolicyState.UNAVAILABLE: RunStatus.POLICY_UNAVAILABLE,
        }
        status = status_by_state.get(decision.state, RunStatus.FAILED)
        return self._finish_with_error(run_id, status, decision.reason_code or status.value)

    def _persist_category_links(
        self,
        session: Session,
        listing: ListingResult,
        category_name: str,
    ) -> None:
        if category_name.count(" > ") >= 2:
            return
        for link in listing.category_links[:12]:
            existing = session.scalar(select(WatchTarget).where(WatchTarget.source_url == link.url))
            if existing is not None:
                continue
            session.add(
                WatchTarget(
                    source_name=self.source_name,
                    target_type="category",
                    label=link.label,
                    source_url=link.url,
                    category=f"{category_name} > {link.label}",
                    priority=4,
                    refresh_interval_hours=72,
                )
            )

    def _finish_with_error(
        self,
        run_id: int,
        status: RunStatus,
        error_code: str,
    ) -> CrawlSummary:
        with self.session_factory.begin() as session:
            return self._finish_in_session(
                session,
                run_id,
                status,
                fetches_created=self._fetch_count(session, run_id),
                error_code=error_code,
            )

    def _finish_in_session(
        self,
        session: Session,
        run_id: int,
        status: RunStatus,
        products_seen: int = 0,
        products_created: int = 0,
        products_updated: int = 0,
        snapshots_created: int = 0,
        details_created: int = 0,
        reviews_created: int = 0,
        fetches_created: int = 0,
        listing_signature: str | None = None,
        error_code: str | None = None,
    ) -> CrawlSummary:
        summary = CrawlSummary(
            run_id=run_id,
            status=status,
            products_seen=products_seen,
            products_created=products_created,
            products_updated=products_updated,
            snapshots_created=snapshots_created,
            details_created=details_created,
            reviews_created=reviews_created,
            fetches_created=fetches_created,
            error_code=error_code,
            listing_signature=listing_signature,
        )
        run = session.get_one(CrawlRun, run_id)
        run.status = status.value
        run.ended_at = datetime.now(UTC)
        run.error_code = error_code
        run.counts_json = json.dumps(
            {
                "products_seen": products_seen,
                "products_created": products_created,
                "products_updated": products_updated,
                "snapshots_created": snapshots_created,
                "details_created": details_created,
                "reviews_created": reviews_created,
                "fetches_created": fetches_created,
            }
        )
        return summary

    @staticmethod
    def _fetch_count(session: Session, run_id: int) -> int:
        return len(session.scalars(select(Fetch.id).where(Fetch.run_id == run_id)).all())

    def _get_or_create_source(self, session: Session) -> Source:
        source = session.scalar(select(Source).where(Source.name == self.source_name))
        if source is None:
            source = Source(
                name=self.source_name,
                base_url=self.source_base_url,
                enabled=True,
                policy_state="unknown",
            )
            session.add(source)
            session.flush()
        return source
