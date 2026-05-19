"""
tests/test_web_browser.py

Unit tests for the Web Browser tool.

Run:
    pytest tests/test_web_browser.py -v
"""

import sys
import os
from unittest.mock import patch, MagicMock

import pytest

# Ensure agents dir is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


from tools.web_browser import (
    validate_url,
    fetch_page,
    web_search,
    _extract_text_from_html,
    _extract_title_from_html,
    _is_private_ip,
)


# ═══════════════════════════════════════════════════════════════════════════
# URL Validation
# ═══════════════════════════════════════════════════════════════════════════

class TestURLValidation:
    def test_valid_https(self):
        ok, _ = validate_url("https://example.com")
        assert ok is True

    def test_valid_http(self):
        ok, _ = validate_url("http://example.com/page")
        assert ok is True

    def test_missing_scheme(self):
        ok, reason = validate_url("example.com")
        assert ok is False
        assert "scheme" in reason.lower()

    def test_file_scheme_blocked(self):
        ok, reason = validate_url("file:///etc/passwd")
        assert ok is False
        assert "blocked" in reason.lower()

    def test_data_scheme_blocked(self):
        ok, reason = validate_url("data:text/html,<h1>hi</h1>")
        assert ok is False

    def test_ftp_blocked(self):
        ok, reason = validate_url("ftp://ftp.example.com/file.txt")
        assert ok is False

    def test_localhost_blocked(self):
        ok, reason = validate_url("http://localhost:8080/admin")
        assert ok is False
        assert "blocked" in reason.lower()

    def test_127_blocked(self):
        ok, reason = validate_url("http://127.0.0.1:3000")
        assert ok is False

    def test_metadata_endpoint_blocked(self):
        ok, reason = validate_url("http://169.254.169.254/latest/meta-data")
        assert ok is False

    def test_no_hostname(self):
        ok, reason = validate_url("http://")
        assert ok is False


# ═══════════════════════════════════════════════════════════════════════════
# Private IP Detection
# ═══════════════════════════════════════════════════════════════════════════

class TestPrivateIPDetection:
    def test_10_range(self):
        assert _is_private_ip("10.0.0.1") is True
        assert _is_private_ip("10.255.255.255") is True

    def test_172_range(self):
        assert _is_private_ip("172.16.0.1") is True
        assert _is_private_ip("172.31.255.255") is True
        assert _is_private_ip("172.15.0.1") is False
        assert _is_private_ip("172.32.0.1") is False

    def test_192_168_range(self):
        assert _is_private_ip("192.168.1.1") is True
        assert _is_private_ip("192.168.2.100") is True

    def test_public_ip(self):
        assert _is_private_ip("8.8.8.8") is False
        assert _is_private_ip("1.1.1.1") is False

    def test_hostname_not_ip(self):
        assert _is_private_ip("example.com") is False


# ═══════════════════════════════════════════════════════════════════════════
# HTML Extraction
# ═══════════════════════════════════════════════════════════════════════════

class TestHTMLExtraction:
    def test_extract_title(self):
        html = "<html><head><title>Test Page</title></head><body></body></html>"
        assert _extract_title_from_html(html) == "Test Page"

    def test_extract_title_missing(self):
        html = "<html><head></head><body></body></html>"
        assert _extract_title_from_html(html) == ""

    def test_extract_text_strips_tags(self):
        html = "<p>Hello <b>World</b></p>"
        text = _extract_text_from_html(html)
        assert "Hello" in text
        assert "World" in text
        assert "<" not in text

    def test_extract_text_strips_scripts(self):
        html = "<p>Before</p><script>alert('xss')</script><p>After</p>"
        text = _extract_text_from_html(html)
        assert "Before" in text
        assert "After" in text
        assert "alert" not in text

    def test_extract_text_strips_styles(self):
        html = "<style>body{color:red}</style><p>Content</p>"
        text = _extract_text_from_html(html)
        assert "Content" in text
        assert "color" not in text

    def test_entity_decoding(self):
        html = "<p>Foo &amp; Bar &lt;baz&gt;</p>"
        text = _extract_text_from_html(html)
        assert "Foo & Bar" in text


# ═══════════════════════════════════════════════════════════════════════════
# Fetch Page (mocked)
# ═══════════════════════════════════════════════════════════════════════════

class TestFetchPage:
    def test_invalid_url_returns_error(self):
        result = fetch_page("not-a-url")
        assert result["error"] is True
        assert "scheme" in result["text"].lower()

    def test_private_ip_blocked(self):
        result = fetch_page("http://192.168.1.1/admin")
        assert result["error"] is True
        assert "private" in result["text"].lower()

    @patch("requests.get")
    def test_successful_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.content = b"<html><head><title>Test</title></head><body><p>Hello World</p></body></html>"
        mock_resp.url = "https://example.com"
        mock_resp.raise_for_status = MagicMock()
        mock_resp.close = MagicMock()
        mock_get.return_value = mock_resp

        result = fetch_page("https://example.com")
        assert result["error"] is False
        assert result["title"] == "Test"
        assert "Hello World" in result["text"]

    @patch("requests.get")
    def test_fetch_timeout(self, mock_get):
        mock_get.side_effect = Exception("Connection timed out")

        result = fetch_page("https://example.com")
        assert result["error"] is True
        assert "timed out" in result["text"].lower()


# ═══════════════════════════════════════════════════════════════════════════
# Web Search (mocked)
# ═══════════════════════════════════════════════════════════════════════════

class TestWebSearch:
    @patch("requests.post")
    def test_search_returns_results(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '''
        <table>
        <tr>
            <td><a rel="nofollow" href="https://example.com/1" class="result-link">Result One</a></td>
        </tr>
        <tr>
            <td class="result-snippet">First result snippet here</td>
        </tr>
        </table>
        '''
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        results = web_search("test query")
        assert len(results) >= 1
        assert results[0]["title"] == "Result One"
        assert results[0]["url"] == "https://example.com/1"

    @patch("requests.post")
    def test_search_failure_returns_empty(self, mock_post):
        mock_post.side_effect = Exception("Network error")
        results = web_search("test query")
        assert results == []
