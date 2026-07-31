import re
import unicodedata

from app.domain.analysis import ReviewSignal

TOPICS = {
    "delivery": (
        "kargo",
        "paket",
        "teslim",
        "gününde",
        "ulaştı",
    ),
    "quality": (
        "kalite",
        "kaliteli",
        "sağlam",
        "kırık",
        "bozuk",
        "malzeme",
    ),
    "price": (
        "fiyat",
        "pahalı",
        "ucuz",
        "uygun",
    ),
    "usability": (
        "kolay",
        "zor",
        "rahat",
        "kullanışlı",
        "kurulum",
    ),
    "safety": (
        "güven",
        "koruy",
        "risk",
        "tehlik",
    ),
}
POSITIVE = (
    "beğendim",
    "güzel",
    "harika",
    "iyi",
    "kaliteli",
    "kolay",
    "rahat",
    "sağlam",
    "tavsiye",
    "teşekkür",
)
NEGATIVE = (
    "bozuk",
    "dayanıksız",
    "geç",
    "iade",
    "kırık",
    "kötü",
    "pahalı",
    "rahatsız",
    "sorun",
    "tehlik",
    "zor",
)
HIGH_SEVERITY = (
    "bozuk",
    "çalışmıyor",
    "iade",
    "kırık",
    "tehlik",
)


def classify_review(text: str) -> tuple[ReviewSignal, ...]:
    normalized = normalize(text)
    positive_hits = matching_terms(normalized, POSITIVE)
    negative_hits = matching_terms(normalized, NEGATIVE)
    topic_hits = {
        topic: matching_terms(normalized, terms)
        for topic, terms in TOPICS.items()
        if matching_terms(normalized, terms)
    }
    if not topic_hits and (positive_hits or negative_hits):
        topic_hits = {"general": positive_hits + negative_hits}
    signals = []
    for topic, terms in topic_hits.items():
        polarity = resolve_polarity(positive_hits, negative_hits)
        severity = resolve_severity(normalized, polarity)
        evidence = evidence_span(text, terms + positive_hits + negative_hits)
        confidence = 0.9 if polarity != "neutral" and topic != "general" else 0.75
        signals.append(
            ReviewSignal(
                topic=topic,
                polarity=polarity,
                severity=severity,
                confidence=confidence,
                evidence_span=evidence,
            )
        )
    return tuple(signals)


def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def matching_terms(value: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(term for term in terms if term in value)


def resolve_polarity(positive: tuple[str, ...], negative: tuple[str, ...]) -> str:
    if negative:
        return "negative"
    if positive:
        return "positive"
    return "neutral"


def resolve_severity(value: str, polarity: str) -> str:
    if polarity != "negative":
        return "low"
    if any(term in value for term in HIGH_SEVERITY):
        return "high"
    return "medium"


def evidence_span(text: str, terms: tuple[str, ...]) -> str:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    for sentence in sentences:
        normalized = normalize(sentence)
        if any(term in normalized for term in terms):
            return sentence[:240]
    return text[:240].strip()
