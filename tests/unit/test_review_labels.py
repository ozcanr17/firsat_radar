from app.analysis.review_labels import classify_review


def test_classify_positive_delivery_review() -> None:
    signals = classify_review("Paketleme çok güzel, ürün bir günde ulaştı. Teşekkür ederim.")

    delivery = next(signal for signal in signals if signal.topic == "delivery")
    assert delivery.polarity == "positive"
    assert delivery.severity == "low"
    assert "Paketleme" in delivery.evidence_span


def test_classify_high_severity_quality_problem() -> None:
    signals = classify_review("Ürün kırık geldi ve iade ettim. Malzeme de kötü.")

    quality = next(signal for signal in signals if signal.topic == "quality")
    assert quality.polarity == "negative"
    assert quality.severity == "high"
    assert quality.confidence == 0.9
