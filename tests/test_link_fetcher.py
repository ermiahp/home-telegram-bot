"""Unit tests for bot/link_fetcher.py."""

from unittest.mock import MagicMock, patch

import pytest

from bot.link_fetcher import LinkInfo, fetch_link_info, is_valid_url


# ---------------------------------------------------------------------------
# is_valid_url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://example.com",
        "https://example.com/path/to/page",
        "https://example.com/path?query=1&foo=bar",
        "https://sub.domain.example.co.uk/page#anchor",
        "https://example.com:8080/path",
    ],
)
def test_is_valid_url_accepts_valid_urls(url):
    assert is_valid_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url",
        "ftp://example.com",
        "example.com",          # missing scheme
        "",
        "   ",
        "javascript:alert(1)",
    ],
)
def test_is_valid_url_rejects_invalid_urls(url):
    assert is_valid_url(url) is False


# ---------------------------------------------------------------------------
# fetch_link_info – unit tests with mocked HTTP
# ---------------------------------------------------------------------------

_SAMPLE_HTML = """<!DOCTYPE html>
<html>
  <head>
    <title>Sample Page</title>
    <meta property="og:title" content="OG Title" />
    <meta property="og:description" content="OG Description" />
    <meta property="og:image" content="https://example.com/image.png" />
    <meta property="og:site_name" content="Example Site" />
    <meta name="description" content="Meta description fallback" />
  </head>
  <body><p>Hello world</p></body>
</html>"""

_HTML_NO_OG = """<!DOCTYPE html>
<html>
  <head>
    <title>Plain Title</title>
    <meta name="description" content="Plain description" />
  </head>
  <body></body>
</html>"""

_HTML_EMPTY = """<!DOCTYPE html><html><head></head><body></body></html>"""


def _make_response(html: str, content_type: str = "text/html; charset=utf-8"):
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.headers = {"Content-Type": content_type}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


@patch("bot.link_fetcher.requests.get")
def test_fetch_link_info_extracts_og_fields(mock_get):
    mock_get.return_value = _make_response(_SAMPLE_HTML)
    info = fetch_link_info("https://example.com")
    assert info.title == "OG Title"
    assert info.description == "OG Description"
    assert info.og_image == "https://example.com/image.png"
    assert info.site_name == "Example Site"
    assert info.url == "https://example.com"


@patch("bot.link_fetcher.requests.get")
def test_fetch_link_info_falls_back_to_title_tag(mock_get):
    mock_get.return_value = _make_response(_HTML_NO_OG)
    info = fetch_link_info("https://example.com")
    assert info.title == "Plain Title"
    assert info.description == "Plain description"
    assert info.og_image is None
    assert info.site_name is None


@patch("bot.link_fetcher.requests.get")
def test_fetch_link_info_empty_html_returns_none_fields(mock_get):
    mock_get.return_value = _make_response(_HTML_EMPTY)
    info = fetch_link_info("https://example.com")
    assert info.title is None
    assert info.description is None


@patch("bot.link_fetcher.requests.get")
def test_fetch_link_info_non_html_returns_url_only(mock_get):
    mock_get.return_value = _make_response("binary data", content_type="application/pdf")
    info = fetch_link_info("https://example.com/doc.pdf")
    assert info.url == "https://example.com/doc.pdf"
    assert info.title is None


def test_fetch_link_info_rejects_non_http_scheme():
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        fetch_link_info("ftp://example.com/file.txt")


@patch("bot.link_fetcher.requests.get")
def test_fetch_link_info_propagates_http_errors(mock_get):
    import requests as req_lib

    mock_get.return_value = _make_response("")
    mock_get.return_value.raise_for_status.side_effect = req_lib.HTTPError("404")
    with pytest.raises(req_lib.HTTPError):
        fetch_link_info("https://example.com/missing")


# ---------------------------------------------------------------------------
# LinkInfo.format_message
# ---------------------------------------------------------------------------


def test_format_message_with_all_fields():
    info = LinkInfo(
        url="https://example.com",
        title="My Title",
        description="My description",
        og_image="https://example.com/img.png",
        site_name="My Site",
    )
    msg = info.format_message()
    assert "My Title" in msg
    assert "My Site" in msg
    assert "My description" in msg
    assert msg.count("example.com") >= 1


def test_format_message_escapes_html():
    info = LinkInfo(url="https://x.com", title="<script>alert('xss')</script>")
    msg = info.format_message()
    assert "<script>" not in msg
    assert "&lt;script&gt;" in msg


def test_format_message_uses_url_when_no_title():
    info = LinkInfo(url="https://example.com/page", title=None)
    msg = info.format_message()
    assert "example.com/page" in msg
