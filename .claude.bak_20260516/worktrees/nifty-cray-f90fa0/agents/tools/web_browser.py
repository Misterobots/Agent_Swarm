"""
Web Browser Tool — Fetch web pages and search the web.

Security:
  - URL validation + domain allowlist (configurable)
  - Content size limits to prevent DoS
  - No JavaScript execution (text-only extraction)
  - Timeout protection
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger("WebBrowser")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_CONTENT_BYTES = int(os.getenv("BROWSER_MAX_CONTENT_BYTES", str(512 * 1024)))  # 512KB
REQUEST_TIMEOUT = int(os.getenv("BROWSER_TIMEOUT", "15"))
USER_AGENT = "HiveAgent/1.0 (Research; +https://github.com/Agent_Swarm)"

# Domain allowlist — empty means allow all non-blocked domains
_ALLOWLIST_RAW = os.getenv("BROWSER_DOMAIN_ALLOWLIST", "")
DOMAIN_ALLOWLIST: set[str] = set(d.strip() for d in _ALLOWLIST_RAW.split(",") if d.strip()) if _ALLOWLIST_RAW else set()

# Always blocked (internal networks, metadata endpoints)
BLOCKED_DOMAINS = {
    "169.254.169.254",   # Cloud metadata
    "metadata.google.internal",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "[::1]",
}

BLOCKED_SCHEMES = {"file", "ftp", "data", "javascript", "vbscript"}


# ---------------------------------------------------------------------------
# URL Validation
# ---------------------------------------------------------------------------
def validate_url(url: str) -> tuple[bool, str]:
    """Validate a URL for safety. Returns (is_valid, reason)."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    if not parsed.scheme:
        return False, "Missing URL scheme (http/https required)"

    if parsed.scheme.lower() in BLOCKED_SCHEMES:
        return False, f"Blocked URL scheme: {parsed.scheme}"

    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Only http/https URLs are allowed, got: {parsed.scheme}"

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False, "Missing hostname"

    # Block internal/metadata endpoints
    if hostname in BLOCKED_DOMAINS:
        return False, f"Blocked domain: {hostname}"

    # Block private IP ranges
    if _is_private_ip(hostname):
        return False, f"Private/internal IP addresses are not allowed: {hostname}"

    # Check allowlist (if configured)
    if DOMAIN_ALLOWLIST:
        if not any(hostname == d or hostname.endswith("." + d) for d in DOMAIN_ALLOWLIST):
            return False, f"Domain not in allowlist: {hostname}"

    return True, "OK"


def _is_private_ip(hostname: str) -> bool:
    """Check if a hostname resolves to a private IP range."""
    # Simple pattern check without DNS resolution
    private_patterns = [
        r"^10\.",
        r"^172\.(1[6-9]|2\d|3[01])\.",
        r"^192\.168\.",
        r"^100\.(6[4-9]|[7-9]\d|1[0-2]\d)\.",  # CGNAT
    ]
    return any(re.match(p, hostname) for p in private_patterns)


# ---------------------------------------------------------------------------
# Text Extraction
# ---------------------------------------------------------------------------
def _extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML, stripping tags and scripts."""
    # Remove script and style blocks
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<noscript[^>]*>.*?</noscript>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Strip all HTML tags
    text = re.sub(r"<[^>]+>", " ", html)

    # Decode common entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def _extract_title_from_html(html: str) -> str:
    """Extract the <title> tag content."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------
def fetch_page(url: str) -> Dict[str, Any]:
    """Fetch a web page and return its text content.

    Returns:
        {
            "url": str,
            "title": str,
            "text": str,
            "content_length": int,
            "error": bool,
        }
    """
    valid, reason = validate_url(url)
    if not valid:
        return {"url": url, "title": "", "text": f"URL validation failed: {reason}", "content_length": 0, "error": True}

    try:
        import requests
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            stream=True,
        )
        resp.raise_for_status()

        # Enforce content size limit
        content_type = resp.headers.get("Content-Type", "")
        content = resp.content[:MAX_CONTENT_BYTES]
        resp.close()

        # Only process text-based content types
        if "text/html" in content_type or "text/plain" in content_type or not content_type:
            try:
                text_content = content.decode("utf-8", errors="replace")
            except Exception:
                text_content = content.decode("latin-1", errors="replace")

            if "text/html" in content_type:
                title = _extract_title_from_html(text_content)
                text = _extract_text_from_html(text_content)
            else:
                title = ""
                text = text_content
        else:
            title = ""
            text = f"[Non-text content: {content_type}, {len(content)} bytes]"

        return {
            "url": str(resp.url),
            "title": title,
            "text": text[:50000],  # Cap text output
            "content_length": len(content),
            "error": False,
        }

    except Exception as e:
        logger.error(f"[WebBrowser] Fetch failed for {url}: {e}")
        return {"url": url, "title": "", "text": f"Fetch error: {e}", "content_length": 0, "error": True}


def web_search(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Search the web using DuckDuckGo Lite (no API key required).

    Returns a list of {"title": ..., "url": ..., "snippet": ...} dicts.
    """
    import requests

    # DuckDuckGo HTML Lite — privacy-respecting, no API key needed
    search_url = "https://lite.duckduckgo.com/lite/"
    try:
        resp = requests.post(
            search_url,
            data={"q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        logger.error(f"[WebBrowser] Search failed: {e}")
        return []

    # Parse DuckDuckGo Lite results (table-based HTML)
    # DDG Lite uses single-quoted class attributes: class='result-link' / class='result-snippet'
    results = []
    link_pattern = re.compile(
        r'<a[^>]+href="([^"]+)"[^>]+class=["\']result-link["\'][^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE,
    )
    snippet_pattern = re.compile(
        r'<td[^>]+class=["\']result-snippet["\'][^>]*>(.*?)</td>',
        re.DOTALL | re.IGNORECASE,
    )

    links = link_pattern.findall(html)
    snippets = snippet_pattern.findall(html)

    for i, (url, title) in enumerate(links[:num_results]):
        clean_title = re.sub(r"<[^>]+>", "", title).strip()
        snippet = ""
        if i < len(snippets):
            snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()
        results.append({
            "title": clean_title,
            "url": url,
            "snippet": snippet,
        })

    return results
