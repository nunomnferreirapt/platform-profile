from platform_profile.extract import extract

from conftest import FIXTURES, ROOT


def test_extract_strips_chrome_and_keeps_content() -> None:
    page = extract((FIXTURES / "index.html").read_text(), f"{ROOT}/")
    assert page.title == "Northwind Field Software | Field data, one platform"
    assert page.text.startswith("# Field data, one platform")
    assert "## What teams use it for" in page.text
    assert "- Offline data capture on tablets" in page.text
    assert "  - Conflict resolution per record" in page.text
    assert "window.track" not in page.text
    assert "Copyright" not in page.text
    assert "Menu" not in page.text


def test_extract_renders_tables_and_quotes() -> None:
    page = extract((FIXTURES / "pricing.html").read_text(), f"{ROOT}/pricing")
    assert "| Plan | Price | Projects |" in page.text
    assert "| --- | --- | --- |" in page.text
    assert "| Team | 59 EUR | Unlimited |" in page.text
    assert "> All plans include offline capture." in page.text
    assert "Footer text" not in page.text


def test_extract_collects_absolute_links_without_fragments_or_mailto() -> None:
    page = extract((FIXTURES / "index.html").read_text(), f"{ROOT}/")
    assert f"{ROOT}/pricing" in page.links
    assert f"{ROOT}/docs/" in page.links
    assert "https://partner.example/northwind" in page.links
    assert not any(link.startswith("mailto:") for link in page.links)
    assert len(page.links) == len(set(page.links))
