"""Discover only the model IDs listed in the platform's Models > Live view."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx


class CatalogError(RuntimeError):
    """Discovery failed; callers must not report a partial catalog as complete."""


# Exact entries from Respan's embedding/audio serving registries, including the
# provider-prefixed aliases those registries create. Some DB rows incorrectly
# retain the default "chat" type, so these registry entries take precedence.
_KNOWN_TYPES = {
    "text-embedding-3-small": "embedding",
    "text-embedding-3-large": "embedding",
    "text-embedding-ada-002": "embedding",
    "openai/text-embedding-3-small": "embedding",
    "openai/text-embedding-3-large": "embedding",
    "openai/text-embedding-ada-002": "embedding",
    "embed-english-v3.0": "embedding",
    "cohere/embed-english-v3.0": "embedding",
    "whisper-1": "audio",
    "openai/whisper-1": "audio",
    "gpt-4o-transcribe": "audio",
    "openai/gpt-4o-transcribe": "audio",
    "tts-1": "audio",
    "openai/tts-1": "audio",
}


def _origin(url: str) -> tuple[str, str | None, int | None]:
    parsed = urlsplit(url)
    return (parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))


def _validate_url(url: str, expected: str) -> None:
    """Never forward the authenticated client to a pagination-supplied host."""
    try:
        parsed = urlsplit(url)
        valid = (
            parsed.scheme in {"https", "http"}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
            and _origin(url) == _origin(expected)
            and parsed.path == urlsplit(expected).path
        )
    except ValueError:
        valid = False
    if not valid:
        # Do not put a server-supplied URL into the error: it may contain secrets.
        raise CatalogError("Catalog URL must use the configured origin and catalog path")


def _get_json(client: httpx.Client, url: str, expected: str) -> dict[str, Any]:
    _validate_url(url, expected)
    try:
        # Override the client's redirect setting: a redirect can move credentials
        # away from the validated catalog endpoint before the next-page check.
        response = client.get(url, follow_redirects=False)
    except httpx.HTTPError:
        raise CatalogError("Catalog request failed before receiving a response") from None
    if response.status_code != 200:
        raise CatalogError(f"Catalog request returned HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        raise CatalogError("Catalog response was not valid JSON") from None
    if not isinstance(payload, dict):
        raise CatalogError("Catalog response must be a JSON object")
    return payload


def _rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        raise CatalogError(f"Catalog response must contain a {key} array")
    for row in rows:
        if not isinstance(row, dict):
            raise CatalogError("Catalog entries must be JSON objects")
        name = row.get("model_name")
        if not isinstance(name, str) or not name.strip():
            raise CatalogError("Catalog entry is missing a nonempty model_name")
    return rows


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    name = row["model_name"]
    provider = row.get("provider")
    if isinstance(provider, dict):
        provider = provider.get("provider_id") or provider.get("provider_name")
    if not isinstance(provider, str) or not provider:
        provider = "unknown"

    # Correct the request type only for entries actually returned by the
    # platform catalog. This mapping never adds models to the test inventory.
    kind = _KNOWN_TYPES.get(name, row.get("model_type", "unknown"))
    if not isinstance(kind, str) or kind not in {"chat", "embedding", "audio"}:
        kind = "unknown"
    reasoning = row.get("reasoning_support")
    # Copy only these fields: provider configuration can contain credentials.
    return {
        "id": name,
        "provider": provider,
        "model_type": kind,
        "reasoning_support": bool(reasoning) if type(reasoning) in (bool, int) and reasoning in (0, 1) else None,
    }


def discover_models(client: httpx.Client, base_url: str) -> list[dict[str, Any]]:
    """Return the platform catalog's active rows, deduplicated by exact name.

    ``base_url`` is the Gateway API root (normally https://api.respan.ai/api).
    ``client`` must carry the caller's Respan API key so org custom models are
    included. The platform labels status=active as Live. Follow every ``next``
    link: ``count`` is THIS PAGE's row count,
    not the size of the catalog. Any failed/malformed page aborts discovery.
    """
    root = base_url.rstrip("/")
    try:
        parsed = urlsplit(root)
    except ValueError:
        raise CatalogError("Gateway base URL is not valid") from None
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise CatalogError("Gateway base URL must not contain credentials, a query, or a fragment")
    list_url = f"{root}/models/list/"
    next_url: str | None = f"{list_url}?status=active&page_size=1000"
    seen_urls: set[str] = set()
    database: dict[str, dict[str, Any]] = {}

    while next_url is not None:
        if next_url in seen_urls:
            raise CatalogError("Catalog pagination repeated a page URL")
        seen_urls.add(next_url)
        payload = _get_json(client, next_url, list_url)
        rows = _rows(payload, "results")
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count != len(rows):
            raise CatalogError("Catalog count must equal the number of rows on its page")
        if "next" not in payload:
            raise CatalogError("Catalog page is missing its next field")
        for row in rows:
            # Match the platform's Live filter. Availability is checked later;
            # verification/billing metadata must not change list membership.
            if row.get("status") == "active":
                database.setdefault(row["model_name"], _normalize(row))
        following = payload["next"]
        if following is not None and (not isinstance(following, str) or not following):
            raise CatalogError("Catalog next must be a nonempty URL or null")
        try:
            next_url = urljoin(next_url, following) if following is not None else None
        except ValueError:
            raise CatalogError("Catalog next URL is not valid") from None

    return [database[name] for name in sorted(database)]
