"""Bounded live collectors for the three source systems.

Collectors use credentials only from environment variables and return normalized
metrics with the exact API URL used as evidence. Cloudflare collection accepts an
export because its analytics schema and account scope are deployment-specific.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .models import Metric


def _get_json(url: str, token: str | None = None) -> Any:
    hostname = (urlparse(url).hostname or "").lower()
    is_github = hostname == "github.com" or hostname.endswith(".github.com")
    headers = {"Accept": "application/vnd.github+json" if is_github else "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=20) as response:  # noqa: S310 - URL is operator configured
        return json.loads(response.read().decode("utf-8"))


def collect_github_org(org: str = "szl-holdings", token: str | None = None) -> list[Metric]:
    token = token or os.getenv("GITHUB_TOKEN")
    observed = datetime.now(timezone.utc)
    repos: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"https://api.github.com/orgs/{org}/repos?{urlencode({'per_page': 100, 'page': page, 'type': 'all'})}"
        batch = _get_json(url, token)
        if not isinstance(batch, list):
            raise ValueError("GitHub repository response must be a list")
        repos.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < 100:
            break
        page += 1
    evidence = f"https://github.com/orgs/{org}/repositories"
    active = sum(not bool(repo.get("archived")) for repo in repos)
    archived = len(repos) - active
    base = {"source": "github", "observed_at": observed, "status": "observed", "evidence_url": evidence}
    return [
        Metric(name="repositories", value=len(repos), unit="count", **base),
        Metric(name="active_repositories", value=active, unit="count", **base),
        Metric(name="archived_repositories", value=archived, unit="count", **base),
    ]


def collect_huggingface_org(org: str = "SZLHOLDINGS", token: str | None = None) -> list[Metric]:
    token = token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    observed = datetime.now(timezone.utc)
    results: list[Metric] = []
    for kind in ("models", "datasets", "spaces"):
        url = f"https://huggingface.co/api/{kind}?{urlencode({'author': org, 'limit': 100, 'full': 'false'})}"
        data = _get_json(url, token)
        if not isinstance(data, list):
            raise ValueError(f"Hugging Face {kind} response must be a list")
        results.append(Metric(
            name=kind, value=len(data), unit="count", source="huggingface", observed_at=observed,
            status="observed", evidence_url=f"https://huggingface.co/{org}",
            note="Bounded public API count; pagination must be enabled if the result reaches the limit.",
        ))
    return results


def load_cloudflare_export(path: Path) -> list[Metric]:
    """Normalize an operator-exported Cloudflare JSON object.

    Expected shape: ``{"metric_name": number, ...}``. The file itself is the
    evidence boundary and must not contain tokens or authorization headers.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Cloudflare export must be a JSON object")
    observed = datetime.now(timezone.utc)
    evidence = str(data.pop("evidence_url", "https://dash.cloudflare.com/"))
    return [
        Metric(name=name, value=value, unit="count", source="cloudflare", observed_at=observed,
               status="observed", evidence_url=evidence)
        for name, value in data.items() if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
