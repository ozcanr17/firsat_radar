import re

ASIN_PATTERN = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", re.IGNORECASE)


def extract_asin(url: str) -> str | None:
    match = ASIN_PATTERN.search(url)
    return match.group(1).upper() if match else None
