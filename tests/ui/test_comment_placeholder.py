from app.ui.listing_app import COMMENT_PLACEHOLDER, VintedListingApp


def test_normalize_comment_returns_empty_for_placeholder() -> None:
    assert VintedListingApp._normalize_comment(COMMENT_PLACEHOLDER) == ""
    assert VintedListingApp._normalize_comment(f"  {COMMENT_PLACEHOLDER}\n") == ""


def test_normalize_comment_preserves_actual_content() -> None:
    comment = "Produit en bon état"
    assert VintedListingApp._normalize_comment(comment) == comment
