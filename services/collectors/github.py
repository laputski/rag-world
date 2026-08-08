"""Сборщик GitHub (STAGE-7 Ф8, план 02 §3.2 — состояние репозитория).

Опрашивает GitHub API по адресу репозитория, извлекает: наличие лицензии,
дату последнего push, наличие выпусков и CI. Возвращает кандидатное свидетельство
типа repository (используется для L3 — «референсная реализация»).

GitHub API: https://api.github.com/repos/{owner}/{repo}
Лицензия: https://api.github.com/repos/{owner}/{repo}/license
Выпуски: https://api.github.com/repos/{owner}/{repo}/releases

CHAOSS-метрики (план 02 [3]): активность, зрелость проекта.
"""

from __future__ import annotations

import re
from datetime import date

from services.collectors.base import CollectResult, HttpGetter, RawEvidence, is_allowed_host

GITHUB_API = "https://api.github.com"


def _extract_repo(url: str) -> tuple[str, str] | None:
    """Извлечь (owner, repo) из GitHub URL или вернуть None."""
    m = re.search(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?(?:$|[?#])", url, re.I)
    if m:
        return m.group(1), m.group(2)
    return None


def _json_get(body: bytes, *path: str) -> str:
    """Безопасное извлечение поля из JSON-ответа."""
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
    """Собрать состояние репозитория из GitHub.

    token — GitHub Personal Access Token (из env GITHUB_TOKEN), без него действует
    жёсткий rate-limit (60 запросов/час). Сбор продолжается без токена, но с
    риском 403.

    Возвращает CollectResult с RawEvidence типа repository, содержащим лицензию,
    дату последнего push, наличие выпусков. verified=False (S5 проверит).
    """
    today = today or date.today()
    result = CollectResult(source_name="github", technology_id=technology_id)

    repo = _extract_repo(repo_url)
    if not repo:
        result.errors.append(f"не удалось извлечь owner/repo из {repo_url!r}")
        return result

    owner, name = repo
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # 1. Основная информация о репозитории.
    repo_api = f"{GITHUB_API}/repos/{owner}/{name}"
    if not is_allowed_host(repo_api):
        result.skipped.append(f"домен вне allowlist: {repo_api}")
        return result

    status, body = http.get(repo_api, headers=headers, timeout=20)
    if status == 404:
        result.errors.append(f"GitHub: репозиторий {owner}/{name} не найден (404)")
        return result
    if status != 200:
        result.errors.append(f"GitHub API вернул {status} для {owner}/{name}")
        return result

    pushed_at = _json_get(body, "pushed_at")[:10]
    license_key = _json_get(body, "license", "key") or "none"
    license_name = _json_get(body, "license", "name") or "No license"

    # 2. Наличие выпусков (releases).
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
    # Глобальная заметка для S5 (лицензия и активность — проверяемые факты).
    result.evidence[-1].expected_title = f"license={license_name}"
    result.evidence[-1].actual_title = f"license={license_name}; pushed_at={pushed_at}"
    return result
