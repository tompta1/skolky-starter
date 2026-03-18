from __future__ import annotations

import re
from typing import Any, Iterable

import requests

ARES_ENDPOINTS = (
    "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty-rs/{ico}",
    "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}",
)

DOMAIN_RE = re.compile(r"^(?:https?://)?(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:/.*)?$", re.I)
BAD_HOST_HINTS = ("ares.gov.cz", "mf.gov.cz")


def normalize_website(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if any(host in text for host in BAD_HOST_HINTS):
        return None
    if not DOMAIN_RE.match(text):
        return None
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    return text


def _walk_json(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            key_norm = key.lower()
            if key_norm in {"www", "website", "web"} and isinstance(child, str):
                website = normalize_website(child)
                if website:
                    yield website
            yield from _walk_json(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)
    elif isinstance(value, str):
        website = normalize_website(value)
        if website:
            yield website


def fetch_website_for_ico(ico: str, timeout: int = 12) -> str | None:
    for template in ARES_ENDPOINTS:
        url = template.format(ico=ico)
        try:
            response = requests.get(url, headers={"Accept": "application/json"}, timeout=timeout)
        except requests.RequestException:
            continue
        if response.status_code != 200:
            continue
        try:
            payload = response.json()
        except ValueError:
            continue
        for website in _walk_json(payload):
            return website
    return None
