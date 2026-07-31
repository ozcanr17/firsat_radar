from app.sources.amazon_tr.parser import extract_asin


def test_extract_asin_from_supported_product_paths() -> None:
    assert extract_asin("https://www.amazon.com.tr/dp/B0D123ABCD") == "B0D123ABCD"
    assert extract_asin("https://www.amazon.com.tr/gp/product/b0d123abcd?ref_=x") == ("B0D123ABCD")
    assert extract_asin("https://www.amazon.com.tr/gp/browse.html?node=12466208031") is None
