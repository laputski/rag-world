"""The package collector: whether a package exists and how often it is taken.

Downloads are one of the two sufficient conditions for the level at which a
technology is used beyond the work that introduced it. Together with presence in
a framework they are the only two machine-readable routes to that level, so
without both collectors the ceiling of collected data stays one level lower.

The package name comes from a field of the record and is **not derived from the
technology's name**. Guessing is inadmissible here: the package index is full of
names resembling names of architectures, and a mistake would yield a level
confirmed by somebody else's downloads. A record without a package name is
passed over in silence, which is an absence of information rather than an error.

The package index does not publish download counts; a separate statistics
service does. When the package is confirmed to exist but the statistics are
unavailable, no downloads evidence is created: the evidence type is called
downloads, and the fact of existence must not be substituted for it.
"""

from __future__ import annotations

import json
from datetime import date

from services.collectors.base import (
    CollectResult,
    HttpGetter,
    RawEvidence,
    is_allowed_host,
)

PYPI_API = "https://pypi.org/pypi"
STATS_API = "https://pypistats.org/api/packages"

#: Below this threshold a month's downloads are not evidence that a technology
#: has spread: the authors' own continuous integration produces about as many.
MIN_MONTHLY_DOWNLOADS = 1000


def _get_json(http: HttpGetter, url: str) -> tuple[dict | None, str | None]:
    if not is_allowed_host(url):
        return None, f"host outside the allowlist: {url}"
    status, body = http.get(url, headers={"User-Agent": "rag-world/0.2"}, timeout=20)
    if status == 404:
        return None, None  # no such package, which is an answer and not a failure
    if status != 200:
        return None, f"status {status} from {url}"
    try:
        return json.loads(body), None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, f"malformed answer from {url}"


def collect_pypi(
    technology_id: str,
    package: str,
    *,
    http: HttpGetter,
    today: date | None = None,
) -> CollectResult:
    """Check that the package exists and collect last month's downloads."""
    today = today or date.today()
    result = CollectResult(source_name="pypi", technology_id=technology_id)

    meta, error = _get_json(http, f"{PYPI_API}/{package}/json")
    if error:
        result.errors.append(f"{technology_id}: {error}")
        return result
    if meta is None:
        result.errors.append(f"{technology_id}: no package {package!r} exists")
        return result

    # The statistics service takes the normalised name: it knows
    # "flagembedding" and does not know "FlagEmbedding".
    stats, error = _get_json(http, f"{STATS_API}/{package.lower()}/recent")
    if error or stats is None:
        # The package exists, the statistics do not. No downloads evidence is
        # created: that a package exists is a different claim.
        result.errors.append(
            f"{technology_id}: download statistics for {package!r} are unavailable"
        )
        return result

    monthly = int((stats.get("data") or {}).get("last_month") or 0)
    if monthly < MIN_MONTHLY_DOWNLOADS:
        result.skipped.append(
            f"{technology_id}: {monthly} downloads a month, below the threshold"
        )
        return result

    version = (meta.get("info") or {}).get("version", "")
    result.evidence.append(RawEvidence(
        technology_id=technology_id,
        type="package_downloads",
        value=f"package={package}; version={version}; downloads_last_month={monthly}",
        source=f"https://pypi.org/project/{package}/",
        fetched_at=today,
        obtained_by="auto",
        verified=False,
    ))
    return result
