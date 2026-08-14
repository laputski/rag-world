#!/usr/bin/env python3
"""The mutation run: a rule counts as guarded when breaking it is caught.

Coverage says a line ran. It does not say that anyone would notice if it broke.
The difference is not hypothetical: the data validation had 48 per cent
coverage, and disabling its checks one at a time left the whole suite green
twenty-one times running.

Here the working code is broken deliberately, one edit at a time, and the whole
suite is run. A mutant that survives marks a place where no check exists,
however much coverage there is.

**The catalogue is written by hand, and that is a decision rather than
laziness.** Random mutation tools produce thousands of edits, most of them
equivalent to the original code: they change nothing in behaviour, they cannot
be killed, and the report drowns in them. Here every entry names the rule it
checks, so the catalogue reads as a list of what the project rests on.

**A mutant that fails to apply counts as a failure, not as a skip.** A line of
code changes, the pattern stops matching, and the entry quietly stops checking
anything. The catalogue stays green meanwhile and looks impressive. That
happened three times in one day, so here it is an error.

Usage::

    python3 scripts/mutate.py                 # the whole catalogue
    python3 scripts/mutate.py --only links    # only the rules about links
    python3 scripts/mutate.py --list          # show the catalogue without running
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Mutation:
    """One deliberate break: the rule it tests and what replaces what."""

    path: str
    rule: str
    before: str
    after: str


# ─── The catalogue ───────────────────────────────────────────────────────────
#
# The order is by subject rather than by importance: that makes an entry easier
# to find by eye and easier to add next to a related one.

MUTATIONS: tuple[Mutation, ...] = (
    # ── The maturity scale: every rule asserts something about a technology ─
    Mutation("core/maturity.py", "L1 requires a publication",
             'l1_ok = _has_publication(evidence, "workshop_preprint")',
             "l1_ok = True"),
    Mutation("core/maturity.py", "L3 requires L2, the scale being monotone",
             'if l3_ok and "L2" in satisfied:', "if l3_ok:"),
    Mutation("core/maturity.py", "L4 counts package downloads",
             '        or _has_any(evidence, "package_downloads")', "        or False"),
    Mutation("core/maturity.py", "confidence is computed, not assigned",
             "return round(sum(per_alt) / len(per_alt), 3) if per_alt else 0.0",
             "return 1.0"),
    Mutation("core/maturity.py", "the freshness of evidence counts",
             "good = sum(1 for e in of_type if _is_fresh(e, as_of) and e.verified)",
             "good = len(of_type)"),

    # ── The dimension schema ────────────────────────────────────────────────
    Mutation("core/dimensions_schema.py", "a configuration is checked against the constraints",
             "def validate(", "def _disabled_validate("),

    # ── The store: duplicates and appending ─────────────────────────────────
    Mutation("services/registry/store.py", "duplicate evidence is filtered out",
             "if key in known:\n            continue",
             "if False:\n            continue"),
    Mutation("services/registry/store.py", "the source is part of a series duplicate key",
             "return (m.technology_id, m.metric, m.measured_at.isoformat(), m.source)",
             "return (m.technology_id, m.metric, m.measured_at.isoformat(), '')"),
    Mutation("services/registry/store.py", "a level is written only when it changes",
             "if previous is not None and previous.level == entry.level:",
             "if False:"),
    Mutation("services/registry/store.py", "evidence is filed by month",
             "by_month.setdefault(evidence_path(item.fetched_at), [])",
             "by_month.setdefault(evidence_path(date(2000, 1, 1)), [])"),

    # ── The fitness of a candidate ──────────────────────────────────────────
    Mutation("core/candidate_fit.py", "a task from the registry subject weighs more",
             'fit.add(4, "coreTask", tasks=core)', 'fit.add(2, "coreTask", tasks=core)'),
    Mutation("core/candidate_fit.py", "a foreign field lowers the score",
             "if off and not core:", "if False:"),
    Mutation("core/candidate_fit.py", "a foreign field does not penalise work on retrieval",
             "if off and not core:", "if off:"),
    Mutation("core/candidate_fit.py", "the score never falls below zero",
             "fit.score = max(0, min(MAX_SCORE, fit.score))",
             "fit.score = min(MAX_SCORE, fit.score)"),
    Mutation("core/candidate_fit.py", "a signal is written as a code, not as a phrase",
             'fit.add(2, "named")', 'fit.signals.append("the work is named") or None'),

    # ── The works-and-code catalogue ────────────────────────────────────────
    Mutation("services/collectors/paperswithcode.py",
             "the catalogue answers about the work that was asked",
             "    if paper.arxiv_id != arxiv_id:", "    if False:"),
    Mutation("services/collectors/paperswithcode.py",
             "the feed is no older than the date requested",
             "        if paper.published < published_after:", "        if False:"),
    Mutation("services/collectors/paperswithcode.py",
             "no venue, no publication evidence",
             "    if not paper.venue:\n        # There is no venue.",
             "    if False:\n        # There is no venue."),
    Mutation("services/collectors/paperswithcode.py",
             "the citation counter is named",
             'parts.append(f"citations_semantic_scholar={paper.citations}")',
             'parts.append(f"cited_by={paper.citations}")'),
    Mutation("services/collectors/paperswithcode.py",
             "the request goes by method tag and date",
             '{"method": method, "published_after": published_after.isoformat()}',
             '{"q": method}'),

    # ── The checks of the collection stage ──────────────────────────────────
    Mutation("services/collectors/s5.py", "the lower bound on a year",
             "MIN_YEAR = 1900", "MIN_YEAR = 0"),

    # ── Attention and its normalisation ─────────────────────────────────────
    Mutation("scripts/build_artifacts.py", "the size threshold of an age subgroup",
             "if len(values) >= MIN_COHORT", "if len(values) >= 0"),
    Mutation("scripts/build_artifacts.py", "the subgroup median, not the mean",
             "year: _median(values)", "year: (sum(values) / len(values))"),
    Mutation("scripts/build_artifacts.py", "a measurement freshness is counted per source",
             "known.measured_at, known.value", "known.value, known.measured_at"),

    # ── Links ───────────────────────────────────────────────────────────────
    Mutation("scripts/check_links.py", "a temporary refusal does not kill a link",
             '    if status in GONE:\n        return "unresolved"',
             '    if status >= 400:\n        return "unresolved"'),
    Mutation("scripts/check_links.py", "a broken connection does not change a link mark",
             'outcomes[link.url] = ("unknown", 0)',
             'outcomes[link.url] = ("unresolved", 0)'),
    Mutation("scripts/check_links.py", "an address closed by rights gets its own link mark",
             '    if status in GUARDED:\n        return "guarded"',
             '    if False:\n        return "guarded"'),

    # ── The digest ──────────────────────────────────────────────────────────
    Mutation("scripts/build_digest.py", "an empty issue is not published",
             "def has_news(self) -> bool:\n        return bool(",
             "def has_news(self) -> bool:\n        return True or bool("),
    Mutation("scripts/build_digest.py", "Russian numerals agree with the count",
             "if 11 <= tail_100 <= 14:", "if False:"),

    # ── The review gate ─────────────────────────────────────────────────────
    Mutation("scripts/classify_changes.py", "the boundary of confirmed evidence",
             'REVIEW_THRESHOLD = "L4"', 'REVIEW_THRESHOLD = "L6"'),
    Mutation("scripts/classify_changes.py", "a demotion requires review",
             "if before is not None and _rank(level) < _rank(before):", "if False:"),
    Mutation("scripts/classify_changes.py", "evidence entered by a person requires review",
             'if entry.get("evidence_basis") == "manual":', "if False:"),
    Mutation("scripts/classify_changes.py", "the comparison is against HEAD, not the index",
             '["git", "diff", "HEAD", "--unified=0", "--", LEVELS_PATH]',
             '["git", "diff", "--unified=0", "--", LEVELS_PATH]'),
    Mutation("scripts/classify_changes.py", "a git failure raises undecidability",
             "if result.returncode != 0:", "if False:"),
    Mutation("scripts/classify_changes.py", "a missing journal raises undecidability",
             "if not (base / LEVELS_PATH).exists():", "if False:"),
    Mutation("scripts/classify_changes.py", "undecidability closes the gate",
             'print("review=true")', 'print("review=false")'),
    Mutation("scripts/classify_changes.py", "the journal path comes from the store",
             "LEVELS_PATH = str(store.LEVELS_FILE.relative_to(ROOT))",
             'LEVELS_PATH = "data/levels/history.jsonl.old"'),

    # ── Data validation ─────────────────────────────────────────────────────
    Mutation("scripts/validate_data.py", "a dimension value exists in the schema",
             "elif value not in ALL_VALUES[code]:", "elif False:"),
    Mutation("scripts/validate_data.py", "a dimension exists in the schema",
             "if code not in ALL_VALUES:\n"
             '                problems.append(f"{where}: неизвестное измерение',
             "if False:\n"
             '                problems.append(f"{where}: неизвестное измерение'),
    Mutation("scripts/validate_data.py", "a configuration breaks no constraint",
             "for error in validate(tech.configuration):", "for error in []:"),
    Mutation("scripts/validate_data.py", "a guarded link carries a date",
             'if link.status in ("verified", "guarded") and link.verified_at is None:',
             "if False:"),
    Mutation("scripts/validate_data.py", "an inapplicable dimension carries no value",
             "elif code in tech.configuration:\n                # Значение у неприменимого",
             "elif False:\n                # Значение у неприменимого"),
    Mutation("scripts/validate_data.py", "a kind without a configuration may hold no values",
             "if tech.kind in store.KINDS_WITHOUT_CONFIGURATION and tech.configuration:",
             "if False:"),
    Mutation("scripts/validate_data.py", "evidence refers to a record that exists",
             "if item.technology_id not in known:", "if False:"),
    Mutation("scripts/validate_data.py", "confidence lies within its interval",
             "if not 0.0 <= entry.confidence <= 1.0:", "if False:"),
    Mutation("scripts/validate_data.py", "a record identifier is not repeated",
             "if tech.id in known:", "if False:"),
    Mutation("scripts/validate_data.py", "a residual comes from the vocabulary",
             "if mechanism not in vocabulary:", "if False:"),
    Mutation("scripts/validate_data.py", "the file name matches the identifier",
             "if declared != path.stem:", "if False:"),
    Mutation("scripts/validate_data.py", "the residual vocabulary is read during validation",
             "vocabulary = _residual_vocabulary()", "vocabulary = {}"),
    Mutation("scripts/validate_data.py", "an identifier follows the convention",
             "if not ID_RE.match(tech.id):", "if False:"),
    Mutation("scripts/validate_data.py", "a record name is not empty",
             "if not tech.name.strip():", "if False:"),
    Mutation("scripts/validate_data.py", "a stratum belongs to A–G",
             "if group not in STRATA:", "if False:"),
    Mutation("scripts/validate_data.py", "a reviewed record asserts something",
             "if (\n            tech.configuration_reviewed", "if (\n            False"),
    Mutation("scripts/validate_data.py", "a dimension is not variable and inapplicable at once",
             "if both:", "if False:"),
    Mutation("scripts/validate_data.py", "a variable dimension has a value",
             "elif code not in tech.configuration:", "elif False:"),
    Mutation("scripts/validate_data.py", "a source has an address",
             "if not link.url.strip():", "if False:"),
    Mutation("scripts/validate_data.py", "a level belongs to the scale",
             "if entry.level not in LEVELS:", "if False:"),

    Mutation(".github/workflows/collect.yml",
             "the pass is rebased onto the branch before it is pushed",
             "          git pull --rebase --autostash origin main\n"
             "          git push\n\n      - name: Commit the changes",
             "          git push\n\n      - name: Commit the changes"),

    # ── Declared dependencies ───────────────────────────────────────────────
    Mutation("pyproject.toml", "the workflow parser dependency is declared",
             '    "pyyaml>=6.0",\n', ""),

    # ── The update pass ─────────────────────────────────────────────────────
    Mutation("scripts/update.py", "the pass stops on a failed validation",
             "if problems:\n        sys.stderr", "if False:\n        sys.stderr"),

    # ── The release: the one irreversible action ────────────────────────────
    Mutation("scripts/make_release.py", "a release validates the data",
             'problems = [f"данные не проходят проверку: {p}" for p in\n'
             "                validate_data.check_registry()]",
             "problems = []"),
    Mutation("scripts/make_release.py", "the artefacts are built from current data",
             "            if expected != actual:", "            if False:"),
    Mutation("scripts/make_release.py", "the artefacts are built at all",
             "    if missing:\n        problems.append(",
             "    if False:\n        problems.append("),
    Mutation("scripts/make_release.py", "a snapshot does not promise a missing file",
             "    if missing:\n        raise FileNotFoundError(",
             "    if False:\n        raise FileNotFoundError("),
    Mutation("scripts/make_release.py", "a release is never rewritten",
             "    if target.exists():\n        raise FileExistsError(",
             "    if False:\n        raise FileExistsError("),
    Mutation("scripts/make_release.py", "a snapshot is written whole or not at all",
             "        os.replace(draft, target)", "        shutil.copytree(draft, target)"),
    Mutation("scripts/make_release.py", "a draft is removed when the write fails",
             "        shutil.rmtree(draft, ignore_errors=True)", "        pass"),
    Mutation("scripts/make_release.py", "a release stops on an obstacle",
             '    if problems:\n        sys.stderr.write(f"выпускать нельзя',
             '    if False:\n        sys.stderr.write(f"выпускать нельзя'),
    Mutation("scripts/make_release.py", "an incomplete release does not pass for a complete one",
             '    if not (target / "release.json").exists():\n        return False',
             "    if False:\n        return False"),
    Mutation("scripts/make_release.py", "the archive counts towards completeness",
             'if not (releases_dir() / f"rag-world-{tag}.zip").exists():\n        return False',
             "if False:\n        return False"),
    Mutation("scripts/make_release.py", "the release index lists the newest first",
             'index.sort(key=lambda r: r["tag"], reverse=True)',
             'index.sort(key=lambda r: r["tag"])'),
    Mutation("scripts/make_release.py", "the description numbers come from the release",
             "f\"{meta['technologies']}, evidence: {meta['evidence']}; a maturity level \"",
             "f\"0, evidence: {meta['evidence']}; a maturity level \""),
    # The reference point has to mean the absence of a technique. The reverse
    # inverts the meaning of the whole portal: inaction is shown as a decision
    # and action as a default, and it all looks like a working page.
    Mutation("core/dimensions_schema.py", "a base value means the absence of a technique",
             '"path_pruning"), default="none"),', '"path_pruning"), default="cross_encoder"),'),

    # The real data has to pass validation in an ordinary test run and not only
    # in the continuous integration job. While no test read it, an edit to a
    # record passed `make test` green and failed after being pushed.
    Mutation("data/technologies/standard_hybridrag.json",
             "the real data is validated by the test run",
             '"verified_at": "2026-08-13"', '"verified_at": null'),

    Mutation("scripts/collect.py", "a digital identifier reaches the open index",
             '    if "doi.org" in url:\n        return ["openalex"]', "    pass"),

    # ── Splitting the code by page ─────────────────────────────────────────
    #
    # The failure here is quiet: the page works, it merely loads more than it
    # needs. Noticing that takes a measurement, and measurements are rare.
    Mutation("ui/public/data/registry.json", "a record is published as a file of its own",
             '"id": "pathrag"', '"id": "pathrag_moved"'),
    Mutation("scripts/build_artifacts.py", "a stale record file is deleted",
             "        (per_record / name).unlink()", "        pass"),

    # ── The mark of the portal and its icons ───────────────────────────────
    #
    # The mark lives as code and the icons as files, and they diverge in
    # silence: the portal shows the new drawing while somebody else's page with
    # a link to it shows the old one.
    Mutation("scripts/build_icons.py", "the icon pattern comes from the mark",
             'block = re.search(r"PATTERN[^=]*=\\s*\\{(?P<body>.*?)\\n\\};", text, re.S)',
             'block = None if text else None'),
    Mutation("scripts/build_icons.py", "the tab icon carries both palettes",
             'f"<style>{light}@media(prefers-color-scheme:dark){{{dark}}}</style>"',
             'f"<style>{light}</style>"'),
    Mutation("scripts/build_icons.py", "the icons are checked against the current mark",
             "if current != payload:", "if current is None:"),
    Mutation("ui/index.html", "the markup links to the preview image",
             '<meta property="og:image" content="https://ragworld.org/og-image.png" />',
             ""),

    # ── Discovery from curated lists ───────────────────────────────────────
    #
    # The source here is not a service with a contract but a file people edit
    # by hand. Hence failures the other collectors do not have: the list changes
    # the shape of its entries, and the parsing silently returns nothing while
    # looking as though it works.
    Mutation("services/collectors/curated.py", "a list changing its shape is noticed",
             'f"{source.name}: the markup arrived and not one entry parsed; "',
             'f"{source.name}: "'),
    Mutation("services/collectors/curated.py",
             "what is known is filtered out before the archive is asked",
             "fresh = [entry for entry in entries if entry.arxiv_id not in known]",
             "fresh = list(entries)"),
    Mutation("services/collectors/curated.py", "a work without an abstract is not entered",
             "            if not detail:", "            if False:"),
    Mutation("services/collectors/curated.py", "parsing invents no entries from arbitrary lines",
             r'    r"^-\s*\((?P<venue>[^)]{1,60})\)\s*\*\*(?P<title>.+?)\*\*"',
             r'    r"^.*?(?P<venue>)(?P<title>\S+)"'),
    Mutation("scripts/discover.py", "recomputation does not lose the curated-list signal",
             'curated_by=row.get("curated_by") or None,', "curated_by=None,"),
    Mutation("core/candidate_fit.py", "inclusion in a list raises fitness",
             'fit.add(2, "curatedList", lists=sorted(curated_by))',
             'fit.add(0, "curatedList", lists=sorted(curated_by))'),

    # ── The localisation of the published data ─────────────────────────────
    #
    # A Russian text without its twin looks like a valid field and is found
    # only by a consumer reading the data without the portal. Prose left behind
    # in the interface resources is not found at all: the published data simply
    # says nothing about what the technology is.
    Mutation("scripts/build_artifacts.py", "the prose reaches the published data",
             '            **prose.get(tech.prose_id or "", {}),', ""),
    Mutation("scripts/build_artifacts.py", "the prose is published in both languages",
             '                out[prose_id][f"{published}_en"] = english',
             "                pass"),
    Mutation("scripts/build_artifacts.py", "the strata are named in English",
             '"name_en": strip(names["en"].get(code, code)),',
             '"name_en": "",'),
    Mutation("scripts/build_artifacts.py", "the English wording of evidence arrives",
             '"value_en": e.value_en,', '"value_en": None,'),
    Mutation("scripts/build_artifacts.py", "the feed is published in both languages",
             '    _write_feed(target / "feed.ru.xml", changes, built_at, _issues(), "ru")',
             "    pass"),

    # ── The machine-readable entrance: index, sitemap, llms.txt ────────────
    #
    # The failure here is doubly quiet. An index promising a dataset that does
    # not exist, and a sitemap missing half the records, both look like valid
    # files; the error surfaces at a consumer who wrote a request from them.
    Mutation("scripts/build_artifacts.py", "the index names every published dataset",
             '    ("digest.json", "issues",',
             '    ("digest_absent.json", "issues",'),
    Mutation("scripts/build_artifacts.py", "the record count comes from the file",
             'entry["records"] = len(payload.get(key, []))',
             'entry["records"] = 0'),
    Mutation("scripts/build_artifacts.py", "the sitemap contains the record pages",
             'urls += [f"{SITE}/tech/{row[\'id\']}" for row in sorted(',
             'urls += [] or [f"{SITE}/tech/nowhere" for row in sorted('),
    Mutation("scripts/build_artifacts.py", "the index carries the version of the level rule",
             '"rule_version": RULE_VERSION,', '"rule_version": "unknown",'),
    Mutation("scripts/build_artifacts.py", "llms.txt discourages scraping the pages",
             '"Do not scrape the pages.', '"Feel free to read the pages.'),
    Mutation("ui/src/i18n/ru.json", "a counted message has every Russian plural form",
             '    "thatDay_few": "{{count}} изменения",\n', ""),

    # ── The prose of the records: the only text of the portal written by hand ─
    #
    # The break is made in the texts rather than in the code: there is nothing
    # here to check but the data, and the guard has to catch exactly that. Every
    # rule repeats a defect the portal has already had.
    Mutation("ui/src/i18n/ru/tech.json", "the prose carries no bibliography references",
             "Microsoft GraphRAG строит по всему",
             "Microsoft GraphRAG [4] строит по всему"),
    Mutation("ui/src/i18n/ru/tech.json", "the prose carries no transliterated jargon",
             "Векторное представление строится по вымышленному ответу",
             "Эмбеддинг строится по вымышленному ответу"),
    Mutation("ui/src/i18n/ru/tech.json", "the prose carries no unexplained abbreviations",
             "которые большая языковая модель извлекает из текста",
             "которые LLM извлекает из текста"),
    Mutation("ui/src/i18n/ru/tech.json", "a dash does not stand in for a verb",
             "а рёбрами служат отношения",
             "а рёбра — отношения"),
    Mutation("ui/src/i18n/ru/tech.json", "a long description is broken into paragraphs",
             "\\n\\nСистема отвечает на вопрос одним из трёх способов",
             " Система отвечает на вопрос одним из трёх способов"),
    Mutation("ui/src/i18n/en/tech.json", "English prose exists wherever Russian prose does",
             '"full": "Microsoft GraphRAG builds a single knowledge graph',
             '"full_": "Microsoft GraphRAG builds a single knowledge graph'),

    Mutation("scripts/make_release.py", "a dry run writes nothing",
             '    if dry_run:\n        print("пробный прогон',
             '    if False:\n        print("пробный прогон'),
)


# ─── The run ─────────────────────────────────────────────────────────────────


def suite_is_green() -> bool:
    """The suite on an untouched tree. Without it, mutants die for other reasons."""
    return _pytest().returncode == 0


def _pytest() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "-x", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
    )


def survives(mutation: Mutation) -> bool | None:
    """True when the mutant survived, False when caught, None when it did not apply."""
    target = ROOT / mutation.path
    original = target.read_text(encoding="utf-8")
    if mutation.before not in original:
        return None
    target.write_text(original.replace(mutation.before, mutation.after, 1),
                      encoding="utf-8")
    try:
        return _pytest().returncode == 0
    finally:
        # Restoration must happen whatever the outcome, an interrupt from the
        # keyboard included: otherwise the broken code stays in the tree.
        target.write_text(original, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="only the rules containing this substring")
    parser.add_argument("--list", action="store_true", help="show the catalogue")
    args = parser.parse_args()

    chosen = [
        m for m in MUTATIONS
        if not args.only
        or args.only.lower() in m.rule.lower()
        or args.only.lower() in m.path.lower()
    ]
    if args.list:
        for mutation in chosen:
            print(f"  {mutation.path:<34} {mutation.rule}")
        print(f"\n{len(chosen)} rules in all")
        return 0
    if not chosen:
        sys.stderr.write(f"nothing matches {args.only!r}\n")
        return 1

    print("checking the untouched tree…", flush=True)
    if not suite_is_green():
        sys.stderr.write(
            "the test suite does not pass without any mutation at all. A "
            "mutation run in this state is meaningless: mutants would die for "
            "reasons of their own. Repair the suite first.\n"
        )
        return 1

    started = time.monotonic()
    survivors: list[Mutation] = []
    unapplied: list[Mutation] = []
    caught = 0

    for index, mutation in enumerate(chosen, 1):
        outcome = survives(mutation)
        head = f"[{index:>2}/{len(chosen)}]"
        if outcome is None:
            unapplied.append(mutation)
            print(f"{head} ?  DID NOT APPLY  {mutation.rule}", flush=True)
        elif outcome:
            survivors.append(mutation)
            print(f"{head} !  SURVIVED       {mutation.rule}", flush=True)
        else:
            caught += 1
            print(f"{head} +  caught         {mutation.rule}", flush=True)

    spent = time.monotonic() - started
    print(
        f"\n{len(chosen)} rules, {caught} caught, {len(survivors)} survived, "
        f"{len(unapplied)} did not apply; in {spent:.0f} s"
    )

    if survivors:
        print("\nUNGUARDED RULES (no test noticed the break):")
        for mutation in survivors:
            print(f"  {mutation.path}: {mutation.rule}")
    if unapplied:
        # Not a skip but a failure: the pattern has drifted from the code, and
        # the entry has stopped checking anything while staying in the catalogue
        # and creating an appearance of a guard.
        print("\nPATTERN DRIFTED FROM THE CODE (the entry checks nothing):")
        for mutation in unapplied:
            print(f"  {mutation.path}: {mutation.rule}")

    return 1 if survivors or unapplied else 0


if __name__ == "__main__":
    raise SystemExit(main())
