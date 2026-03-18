"""
Unit tests for app.ares — no network required (requests.get is mocked).
"""
from unittest.mock import MagicMock, patch

import pytest

from app.ares import _walk_json, fetch_website_for_ico, normalize_website


# ── normalize_website ──────────────────────────────────────

def test_normalize_none_returns_none():
    assert normalize_website(None) is None


def test_normalize_empty_string_returns_none():
    assert normalize_website("") is None


def test_normalize_whitespace_only_returns_none():
    assert normalize_website("   ") is None


def test_normalize_gov_domain_hint_returns_none():
    assert normalize_website("https://ares.gov.cz/some/path") is None


def test_normalize_garbage_returns_none():
    assert normalize_website("not a url at all!!!") is None


def test_normalize_valid_http_url_returned_as_is():
    assert normalize_website("http://www.skola.cz") == "http://www.skola.cz"


def test_normalize_no_scheme_prepends_https():
    assert normalize_website("www.skola.cz") == "https://www.skola.cz"


def test_normalize_trailing_slash_returned_as_is():
    assert normalize_website("https://www.skola.cz/") == "https://www.skola.cz/"


def test_normalize_mixed_case_scheme_prepends_https():
    # startswith check is case-sensitive, so HTTP:// gets https:// prepended
    result = normalize_website("HTTP://foo.cz")
    assert result == "https://HTTP://foo.cz"


# ── _walk_json ─────────────────────────────────────────────

def test_walk_json_www_key_yields_website():
    result = list(_walk_json({"www": "https://skola.cz"}))
    assert "https://skola.cz" in result


def test_walk_json_website_key_yields_website():
    result = list(_walk_json({"website": "https://skola.cz"}))
    assert "https://skola.cz" in result


def test_walk_json_nested_dict_recurses():
    result = list(_walk_json({"outer": {"www": "https://nested.cz"}}))
    assert "https://nested.cz" in result


def test_walk_json_list_of_strings_yields_valid_urls():
    result = list(_walk_json(["https://a.cz", "not-a-url!!!", "https://b.cz"]))
    assert "https://a.cz" in result
    assert "https://b.cz" in result
    assert len(result) == 2


def test_walk_json_plain_valid_string_yields_it():
    result = list(_walk_json("https://plain.cz"))
    assert result == ["https://plain.cz"]


def test_walk_json_no_url_yields_nothing():
    result = list(_walk_json({"foo": "bar", "baz": 42}))
    assert result == []


# ── fetch_website_for_ico ──────────────────────────────────

def _mock_response(status_code: int, json_body=None, raise_exc=None):
    mock = MagicMock()
    mock.status_code = status_code
    if raise_exc:
        mock.json.side_effect = raise_exc
    elif json_body is not None:
        mock.json.return_value = json_body
    return mock


def test_fetch_website_first_endpoint_succeeds():
    payload = {"www": "https://skola.cz"}
    with patch("app.ares.requests.get") as mock_get:
        mock_get.return_value = _mock_response(200, json_body=payload)
        result = fetch_website_for_ico("12345678")
    assert result == "https://skola.cz"
    assert mock_get.call_count == 1


def test_fetch_website_first_404_second_succeeds():
    payload = {"website": "https://druha.cz"}
    with patch("app.ares.requests.get") as mock_get:
        mock_get.side_effect = [
            _mock_response(404),
            _mock_response(200, json_body=payload),
        ]
        result = fetch_website_for_ico("12345678")
    assert result == "https://druha.cz"
    assert mock_get.call_count == 2


def test_fetch_website_both_raise_request_exception_returns_none():
    import requests as req_lib
    with patch("app.ares.requests.get", side_effect=req_lib.RequestException("timeout")):
        result = fetch_website_for_ico("12345678")
    assert result is None


def test_fetch_website_non_json_body_returns_none():
    with patch("app.ares.requests.get") as mock_get:
        mock_get.return_value = _mock_response(200, raise_exc=ValueError("not json"))
        result = fetch_website_for_ico("12345678")
    assert result is None
