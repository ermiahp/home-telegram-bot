"""Fetch a URL and extract metadata (title, description, Open Graph tags)."""

import re
from dataclasses import dataclass, field
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# Reasonable timeout so the bot stays responsive
_REQUEST_TIMEOUT = 10

# Simple URL validation pattern
_URL_RE = re.compile(
    r"^https?://"  # scheme
    r"(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)"  # subdomains
    r"+[A-Z]{2,}"  # TLD
    r"(?::\d+)?"  # optional port
    r"(?:[/?#]\S*)?$",
    re.IGNORECASE,
)


@dataclass
class LinkInfo:
    """Structured information extracted from a URL."""

    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    og_image: Optional[str] = None
    site_name: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)

    def format_message(self) -> str:
        """Return a Telegram-ready text summary of the link info."""
        lines = [f"🔗 <b>{_escape(self.title or self.url)}</b>"]
        if self.site_name:
            lines.append(f"🌐 {_escape(self.site_name)}")
        if self.description:
            lines.append(f"\n{_escape(self.description)}")
        lines.append(f"\n<a href=\"{self.url}\">Open link</a>")
        return "\n".join(lines)


def _escape(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def is_valid_url(text: str) -> bool:
    """Return True if *text* looks like an HTTP/HTTPS URL."""
    return bool(_URL_RE.match(text.strip()))


def fetch_link_info(url: str) -> LinkInfo:
    """Fetch *url* and return a :class:`LinkInfo` with extracted metadata.

    Raises :class:`requests.RequestException` on network / HTTP errors.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme!r}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; HomeTelegramBot/1.0; "
            "+https://github.com/ermiahp/home-telegram-bot)"
        )
    }

    response = requests.get(url, headers=headers, timeout=_REQUEST_TIMEOUT)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower():
        # Non-HTML resource – just return the URL
        return LinkInfo(url=url)

    soup = BeautifulSoup(response.text, "lxml")

    def _og(property_name: str) -> Optional[str]:
        tag = soup.find("meta", attrs={"property": property_name})
        if tag and tag.get("content"):  # type: ignore[union-attr]
            return str(tag["content"]).strip()  # type: ignore[index]
        return None

    def _meta_name(name: str) -> Optional[str]:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):  # type: ignore[union-attr]
            return str(tag["content"]).strip()  # type: ignore[index]
        return None

    title = (
        _og("og:title")
        or (soup.title.string.strip() if soup.title and soup.title.string else None)
        or _meta_name("title")
    )
    description = _og("og:description") or _meta_name("description")
    og_image = _og("og:image")
    site_name = _og("og:site_name")

    return LinkInfo(
        url=url,
        title=title,
        description=description,
        og_image=og_image,
        site_name=site_name,
    )
