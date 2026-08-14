"""The code-hosting collector: the state of a repository.

Asks the hosting interface about a repository and extracts the licence, the date
of the last push and whether releases exist. It returns candidate evidence of
the repository type, which is what the maturity rule reads for the level that
requires a reference implementation.
"""

from __future__ import annotations

import re
from datetime import date

from services.collectors.base import CollectResult, HttpGetter, RawEvidence, is_allowed_host

GITHUB_API = "https://api.github.com"


def _extract_repo(url: str) -> tuple[str, str] | None:
    """Pull (owner, repo) out of a repository URL, or return None."""
    m = re.search(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?(?:$|[?#])", url, re.I)
    if m:
        return m.group(1), m.group(2)
    return None


def _json_get(body: bytes, *path: str) -> str:
    """Read a field out of a JSON answer without trusting its shape."""
    import json

    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ""
    cur: object = data
    for key in path:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return ""
    return str(cur) if cur is not None else ""


def collect_github(
    technology_id: str,
    repo_url: str,
    *,
    http: HttpGetter,
    token: str | None = None,
    today: date | None = None,
) -> CollectResult:
    """Collect the state of a repository from the code hosting service.

    The token raises the rate limit, which without one is sixty requests an
    hour. Collection proceeds without a token and simply risks a refusal.

    Returns evidence of the repository type carrying the licence, the date of
    the last push and whether releases exist. The cross-check stage decides
    whether it counts as verified.
    """
    today = today or date.today()
    result = CollectResult(source_name="github", technology_id=technology_id)

    repo = _extract_repo(repo_url)
    if not repo:
        result.errors.append(f"no owner/repo could be read from {repo_url!r}")
        return result

    owner, name = repo
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # The repository itself.
    repo_api = f"{GITHUB_API}/repos/{owner}/{name}"
    if not is_allowed_host(repo_api):
        result.skipped.append(f"host outside the allowlist: {repo_api}")
        return result

    status, body = http.get(repo_api, headers=headers, timeout=20)
    if status == 404:
        result.errors.append(f"no repository {owner}/{name} exists (404)")
        return result
    if status != 200:
        result.errors.append(f"the code host answered {status} for {owner}/{name}")
        return result

    pushed_at = _json_get(body, "pushed_at")[:10]
    license_key = _json_get(body, "license", "key") or "none"
    license_name = _json_get(body, "license", "name") or "No license"

    # Whether releases exist.
    releases_api = f"{GITHUB_API}/repos/{owner}/{name}/releases?per_page=1"
    rel_status, rel_body = http.get(releases_api, headers=headers, timeout=20)
    has_releases = False
    if rel_status == 200:
        import json
        try:
            has_releases = len(json.loads(rel_body)) > 0
        except (json.JSONDecodeError, UnicodeDecodeError):
            has_releases = False

    value = (
        f"{owner}/{name}: license={license_key}, last_push={pushed_at}, "
        f"releases={'yes' if has_releases else 'no'}"
    )
    result.evidence.append(RawEvidence(
        technology_id=technology_id,
        type="repository",
        value=value,
        source=f"https://github.com/{owner}/{name}",
        fetched_at=today,
        obtained_by="auto",
        verified=False,
    ))
    # What the cross-check stage compares: the licence and the activity are
    # both checkable facts.
    result.evidence[-1].expected_title = f"license={license_name}"
    result.evidence[-1].actual_title = f"license={license_name}; pushed_at={pushed_at}"
    return result
