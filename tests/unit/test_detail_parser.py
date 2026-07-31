from datetime import UTC, datetime

from app.sources.hepsiburada.detail_parser import (
    RenderedProductDetail,
    RenderedReview,
    build_review_evidence,
    parse_product_detail,
    parse_reviews,
)


def test_parse_product_detail_with_coverage_and_attributes() -> None:
    parsed = parse_product_detail(
        RenderedProductDetail(
            title="Karf Momsafe",
            brand="Karf",
            seller="Karf",
            description="Görünür açıklama",
            product_info_text=(
                "Ürün özellikleri\nMenşei\nTR - Türkiye\nStok Adedi\n10.000 adetten az\n"
                "Yurt Dışı Satış\nYok\nStok Kodu\nHBCV0001"
            ),
            review_url="https://www.hepsiburada.com/urun-p-HBCV0001-yorumlari",
        )
    )

    assert parsed.coverage == 1.0
    assert parsed.origin == "TR - Türkiye"
    assert parsed.stock == "10.000 adetten az"
    assert parsed.overseas_sale == "Yok"
    assert parsed.reason_codes == ()


def test_reviews_exclude_identity_and_redact_direct_identifiers() -> None:
    observed_at = datetime(2026, 7, 31, tzinfo=UTC)
    reviews = parse_reviews(
        [
            RenderedReview(
                date_text="27 Ocak, Sal",
                text="İletişim 0555 111 22 33 ve test@example.com, ürün çok iyi.",
            )
        ],
        "https://www.hepsiburada.com/urun-p-HBCV0001",
        "https://www.hepsiburada.com/urun-p-HBCV0001-yorumlari",
        observed_at,
    )
    evidence = build_review_evidence(reviews)

    assert len(reviews) == 1
    assert reviews[0].review_date == datetime(2026, 1, 27, tzinfo=UTC)
    assert "0555" not in reviews[0].text_redacted
    assert "example.com" not in reviews[0].text_redacted
    assert "[TELEFON]" in reviews[0].text_redacted
    assert "[E-POSTA]" in reviews[0].text_redacted
    assert "reviewer" not in evidence
    assert 'data-identity-redacted="true"' in evidence
