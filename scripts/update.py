#!/usr/bin/env python3
"""Update the portal in a single pass.

The only entry point of the chain. A person uses it through `make collect` and
the schedule uses it directly, so what the unattended run does matches what a
local run does by construction, and the workflow stays a wrapper with no logic
in it.

The order of the steps, and why it is this one:

1. **Collection** — the sources are asked, the deterministic checks run, and
   evidence and measurements are appended. A source refusing does not interrupt
   the pass: the remaining records are processed and the refusal reaches the run
   log.
2. **Links** — whether the registry's addresses resolve. A link rots in silence,
   and a record with no live source goes on looking grounded. A temporary
   refusal does not change the mark: publishers refuse robots, and taking that
   for the death of a link would spoil the registry faster than time spoils
   addresses.
3. **Discovery** — the catalogue is asked for the past week under the method
   tag. It creates no registry records and appends candidates to a queue where a
   person decides. A work that has been found is a supposition about a
   technology, not a technology.
4. **Levels** — recomputed by the rule, with no language model. Only a change
   reaches the level journal.
5. **Artefacts** — what the portal reads is rebuilt. The build is stable: with
   unchanged data the files come out byte for byte the same, so no spurious
   changes arise.
6. **Validation** — schema, references, the provenance of numbers. It runs
   **always**, even when the data did not change: it is cheap and it catches
   corruption rather than only an update. A failure ends the pass with an error,
   and it does so **before** anything is committed.
7. **The run log** — one line, always. It distinguishes "nobody looked" from
   "nothing happened" and serves as the sign of activity the platform wants: a
   schedule is disabled after sixty days without commits.
8. **The watch over the chronicle** — whether the level journal has moved at
   all while the passes kept bringing evidence. It stops nothing and fails
   nothing: a scale standing still is a legitimate state, and the watch only
   says that it has stood still long enough to be worth asking about.
9. **The digest** — an issue about what changed, when anything did. No language
   model takes part: an issue retells what has already been computed, and there
   is nothing in it to invent. An empty issue is not published — the question
   whether anyone looked is answered by the run log, and the digest answers the
   question of what was found.

Usage::

    python3 scripts/update.py                 # the whole pass
    python3 scripts/update.py --limit 5       # the first five records, as a trial
    python3 scripts/update.py --only pathrag  # one record
    python3 scripts/update.py --skip-collect  # recomputation and build only
    python3 scripts/update.py --dry-run       # write nothing
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.registry import store  # noqa: E402

#: How often to recheck a link already confirmed. A month trades the cost to
#: somebody else's resources against how long a breakage stays unnoticed.
LINK_RECHECK_DAYS = 30


def run(
    *,
    limit: int = 0,
    only: str | None = None,
    skip_collect: bool = False,
    dry_run: bool = False,
    http=None,
    #: A separate transport for the links: its allowlist is lifted, because the
    #: registry points at venues outside it.
    link_http=None,
    today: date | None = None,
) -> int:
    import build_artifacts
    import build_digest
    import check_links
    import collect
    import compute_levels
    import validate_data
    import watch_chronicle

    today = today or date.today()

    # ─── 1. Collection ───────────────────────────────────────────────────────
    if skip_collect:
        gathered = collect.CollectSummary()
    else:
        gathered = collect.gather(
            limit=limit, only=only, dry_run=dry_run, http=http, today=today
        )
        print(
            f"collected: evidence {gathered.evidence_added}, "
            f"series points {gathered.metrics_added}; "
            f"rejected by the checks {gathered.rejected}; "
            f"sources that yielded nothing {len(gathered.errors)}"
        )
        if gathered.failures:
            print("  refusals by source: " + ", ".join(
                f"{source} {count}"
                for source, count in sorted(gathered.failures.items())
            ))
        for message in gathered.errors[:10]:
            print(f"  {message[:130]}")
        if len(gathered.errors) > 10:
            print(f"  and {len(gathered.errors) - 10} more")

    # ─── 2. Links ────────────────────────────────────────────────────────────
    #
    # Links rot in silence: a venue moves, a preprint is withdrawn, a repository
    # is renamed, and the record goes on looking grounded. The check runs after
    # collection, because collection may have added sources, and before levels
    # are recomputed, so that a broken link shows up in the same pass.
    #
    # Recently confirmed addresses are skipped: a link opened yesterday rarely
    # vanishes within a week, and the extra requests spend somebody else's
    # resources.
    if not skip_collect:
        links = check_links.run(
            http=link_http, today=today, dry_run=dry_run,
            stale_after=LINK_RECHECK_DAYS,
        )
        print(
            f"links: checked {links.checked}, resolving {links.verified}, "
            f"gone {links.gone}, closed by rights {links.guarded}"
        )
        for problem in links.problems[:10]:
            print(f"  {problem[:130]}")
        if len(links.problems) > 10:
            print(f"  and {len(links.problems) - 10} more")
    else:
        links = check_links.LinkSummary()

    # ─── 3. Discovery ────────────────────────────────────────────────────────
    #
    # It creates no records: it appends candidates to a queue where a person's
    # verdict awaits them. A refusal from the catalogue does not interrupt the
    # pass, any more than a refusal from any other source does.
    if not skip_collect:
        import discover

        found = discover.run(http=http, today=today, dry_run=dry_run)
        print(
            f"discovery: found {found.found}, added to the queue "
            f"{found.added}, already in the registry {found.known}"
        )
        # What a check dropped is reported apart from what a source refused. The
        # count is large and steady, because the mirror ignores the date it is
        # asked for; reported as refusals it hid the handful of real ones.
        if found.discarded:
            print(
                f"  works the window check dropped: {len(found.discarded)}; "
                f"first of them: {found.discarded[0][:100]}"
            )
        # The messages are printed here rather than with the collection ones:
        # that print has already run by now, and without this the refusals of
        # the catalogue reached the count in the run log and no eye at all.
        for message in found.problems[:10]:
            print(f"  {message[:130]}")
        if len(found.problems) > 10:
            print(f"  and {len(found.problems) - 10} more")
        # The refusals are attributed to the source that made them rather than
        # to the step: discovery asks the works-and-code catalogue and the
        # curated lists, and a step is not a source. The messages and the counts
        # are added apart, because discovery already knows which source each
        # count belongs to while the messages carry no such mark.
        gathered.errors.extend(found.problems)
        gathered.failures.update(found.failures)
    else:
        found = None

    # ─── 4. Levels ───────────────────────────────────────────────────────────
    levels_changed = compute_levels.run(dry_run=dry_run, today=today)

    # ─── 5. Artefacts ────────────────────────────────────────────────────────
    if not dry_run:
        counts = build_artifacts.build()
        print(
            f"artefacts: technologies {counts['technologies']}, "
            f"chronicle entries {counts['changes']}"
        )

    # ─── 6. Validation ───────────────────────────────────────────────────────
    problems = validate_data.check_registry()
    if problems:
        sys.stderr.write(f"data validation failed: {len(problems)} problems\n")
        for problem in problems[:20]:
            sys.stderr.write(f"  {problem}\n")
        # Return with an error before anything is committed: spoiled data must
        # not be published.
        return 1
    print("data validation passed")

    # ─── 7. The run log ──────────────────────────────────────────────────────
    #
    # A pass that polled no sources does not reach the collection log: a line
    # saying "checked on such a date" with an empty list of sources would assert
    # a check that never happened. Such a pass is a rebuild after a code edit,
    # not a collection.
    if not dry_run and not skip_collect:
        store.append_run(store.CollectionRun(
            ran_at=today,
            sources=gathered.sources,
            evidence_added=gathered.evidence_added,
            metrics_added=gathered.metrics_added,
            levels_changed=levels_changed,
            source_errors=len(gathered.errors),
            failed_sources=dict(sorted(gathered.failures.items())),
            links_checked=links.checked,
            links_broken=links.gone,
            data_changed=bool(
                gathered.evidence_added or gathered.metrics_added
                or levels_changed or links.changed
            ),
        ))
        print(f"the pass is recorded in {store.COLLECTION_LOG.name}")

        # ─── 8. The watch over the chronicle ─────────────────────────────────
        #
        # After the run log, so that the pass just finished counts among the
        # silent ones; a watch that lagged a week behind would report a state
        # nobody could act on yet.
        #
        # It does not end the pass with an error. A chronicle standing still is
        # not spoiled data, and stopping the pass over it would block a run that
        # has nothing wrong with it. What it does is say so out loud, because
        # until it is said the silence is indistinguishable from normality.
        #
        # It speaks in both cases, and deliberately. A watch heard only when it
        # sounds leaves a reader of the log unable to tell a quiet watch from
        # one that was never wired in, which is the same confusion the run log
        # itself exists to end.
        silence = watch_chronicle.look(store.load_runs(), store.load_levels())
        print(
            f"watch: {silence.message()}" if silence is not None
            else "watch: the chronicle is moving, or nothing arrived to move it"
        )

        # ─── 9. The digest ───────────────────────────────────────────────────
        #
        # After the run log, because an issue reports the link check as well,
        # and after validation, because an issue must not be published from
        # spoiled data. No language model takes part: an issue retells what has
        # already been computed, and there is nothing in it to invent — which is
        # exactly why it is published without review by a person.
        #
        # An empty issue is not published: a week without changes is an ordinary
        # thing, and fifty messages saying nothing happened would turn the digest
        # into noise. The question of whether anyone looked is answered by the
        # run log.
        issue = build_digest.build(today=today)
        if issue.has_news():
            path = build_digest.digest_dir() / f"{issue.issued_at.isoformat()}.json"
            if path.exists():
                print("a digest issue for today already exists, no second one")
            else:
                build_digest.publish(issue)
                print(f"digest issue: {path.name}")
                # The feed and the issues page read the built files, so the
                # artefacts are rebuilt: without that the issue would sit in the
                # data and never reach a reader.
                build_artifacts.build()
        else:
            print("digest: nothing changed, no issue built")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="cap the number of records")
    parser.add_argument("--only", help="process one named record")
    parser.add_argument(
        "--skip-collect", action="store_true",
        help="poll no sources, only recompute and rebuild",
    )
    parser.add_argument("--dry-run", action="store_true", help="write nothing")
    args = parser.parse_args()
    return run(
        limit=args.limit,
        only=args.only,
        skip_collect=args.skip_collect,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
