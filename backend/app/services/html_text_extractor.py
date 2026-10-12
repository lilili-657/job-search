"""Deterministic HTML-to-text extraction without semantic interpretation."""

from bs4 import BeautifulSoup


def extract_visible_text(raw_html: str) -> str:
    """Return text in document order with whitespace normalized to spaces.

    Excludes scripts, styles, head metadata, templates, comments, and elements
    with the HTML hidden attribute. Does not execute JavaScript or evaluate CSS;
    this is basic text extraction, not browser-rendered visibility detection.
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    # Remove children before parents when excluded elements are nested.
    for element in reversed(soup.select("script, style, head, template, [hidden]")):
        element.decompose()
    return " ".join(soup.get_text(separator=" ", strip=True).split())
