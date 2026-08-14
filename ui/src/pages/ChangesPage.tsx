import { useEffect, useMemo, useState } from "react";
import {
  Alert, Box, Chip, CircularProgress, Collapse, Link as MuiLink, Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getChanges } from "../api/client";
import type { RegistryChange } from "../api/types";
import { MONO } from "../theme";
import { useDocumentHead } from "../useDocumentHead";

/**
 * The chronicle of registry changes.
 *
 * The freshness of the portal is proved by a list of changes rather than by a
 * build date. Every chronicle entry therefore carries the former and the new
 * level and the evidence that led to the change: a claim of a change without
 * grounds is no better than no chronicle at all.
 *
 * The order of presentation follows how the page is read. A reader first wants
 * to know how much happened and whether a demotion was among it, and only then
 * works through the individual entries. So the counts by kind stand at the top
 * and the entries are gathered by date: eighty-seven rows with a repeated date
 * read as one uniform sheet, whereas four dates with a count beside each are
 * taken in at a glance.
 *
 * The grounds are collapsed. They have to be available, or a change is
 * unprovable, but expanded they took more room than the change itself and
 * crowded it out. One click opens them, and collapsed they still say how many
 * there are and of what kind.
 */

const WINDOWS = [
  { key: "week", days: 7 },
  { key: "month", days: 31 },
  { key: "all", days: 0 },
] as const;

/** The kinds of change in order of importance: a demotion is read first. */
const KINDS = ["level_down", "level_up", "added"] as const;

const KIND_LABEL: Record<string, string> = {
  level_up: "changes.levelUp",
  level_down: "changes.levelDown",
  added: "changes.added",
};

/**
 * The colour of a kind of change.
 *
 * A demotion is the one event on the portal that means an earlier claim turned
 * out to be wrong, and it has to be seen before anything else. A promotion and
 * a record appearing are ordinary and carry no colour.
 */
function kindColor(kind: string): "warning.main" | "text.secondary" {
  return kind === "level_down" ? "warning.main" : "text.secondary";
}

export function ChangesPage() {

  const { t } = useTranslation();
  useDocumentHead({
    title: t("head.changes.title"),
    description: t("head.changes.description"),
  });
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [changes, setChanges] = useState<RegistryChange[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const window = params.get("window") ?? "month";

  useEffect(() => {
    getChanges()
      .then((res) => { setChanges(res.changes); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const visible = useMemo(() => {
    const days = WINDOWS.find((w) => w.key === window)?.days ?? 0;
    if (!days) return changes;
    const since = new Date();
    since.setDate(since.getDate() - days);
    return changes.filter((c) => new Date(c.changed_at) >= since);
  }, [changes, window]);

  /** The counts by kind of change over the chosen period. */
  const tally = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const change of visible) counts[change.kind] = (counts[change.kind] ?? 0) + 1;
    return KINDS.filter((kind) => counts[kind]).map((kind) => ({ kind, count: counts[kind] }));
  }, [visible]);

  /** The changes gathered by date, the newest days on top. */
  const byDate = useMemo(() => {
    const groups = new Map<string, RegistryChange[]>();
    for (const change of visible) {
      const day = groups.get(change.changed_at) ?? [];
      day.push(change);
      groups.set(change.changed_at, day);
    }
    return [...groups.entries()]
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([date, items]) => ({
        date,
        // Within a day demotions come first for the same reason they are
        // coloured: they are the one thing a reader must not miss.
        items: [...items].sort(
          (a, b) => KINDS.indexOf(a.kind as never) - KINDS.indexOf(b.kind as never)
        ),
      }));
  }, [visible]);

  return (
    <Box sx={{ maxWidth: 900 }}>
      <Typography variant="h2" sx={{ mb: 0.5 }}>{t("changes.title")}</Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
        {t("changes.subtitle")}
      </Typography>

      <Box sx={{
        display: "flex", gap: 2.5, py: 1,
        borderTop: 1, borderBottom: 1, borderColor: "divider",
      }}>
        {WINDOWS.map((w) => (
          <Typography
            key={w.key}
            onClick={() => {
              const next = new URLSearchParams(params);
              next.set("window", w.key);
              setParams(next, { replace: true });
            }}
            sx={{
              fontSize: "0.85rem", cursor: "pointer",
              color: window === w.key ? "text.primary" : "text.secondary",
              fontWeight: window === w.key ? 600 : 400,
            }}
          >
            {t(`changes.window.${w.key}`)}
          </Typography>
        ))}
      </Box>

      {/*
        The counts by kind stand before the entries and answer the question
        people come to the page with: how much happened, and was there a demotion
        among it. Without them the answer took scrolling through the whole
        chronicle.
      */}
      {!loading && !error && visible.length > 0 && (
        <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap", py: 1.5 }}>
          {tally.map(({ kind, count }) => (
            <Box key={kind}>
              <Typography
                className="tabular"
                sx={{ fontSize: "1.5rem", lineHeight: 1.1, color: kindColor(kind) === "warning.main" ? "warning.main" : "text.primary" }}
              >
                {count}
              </Typography>
              <Typography variant="caption" sx={{ color: kindColor(kind) }}>
                {t(KIND_LABEL[kind])}
              </Typography>
            </Box>
          ))}
          <Box sx={{ ml: "auto", textAlign: "right" }}>
            <Typography className="tabular" sx={{ fontSize: "1.5rem", lineHeight: 1.1 }}>
              {byDate.length}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {t("changes.daysWithChanges", { count: byDate.length })}
            </Typography>
          </Box>
        </Box>
      )}

      {error && <Alert severity="info">{t("changes.unavailable")}</Alert>}
      {loading && <CircularProgress sx={{ display: "block", mx: "auto", my: 6 }} />}
      {!loading && !error && visible.length === 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>
          {t("changes.empty")}
        </Typography>
      )}

      {byDate.map(({ date, items }) => (
        <Box key={date} sx={{ mt: 3 }}>
          <Box sx={{
            display: "flex", alignItems: "baseline", gap: 1.5,
            borderBottom: 1, borderColor: "divider", pb: 0.5, mb: 0.5,
          }}>
            <Typography className="tabular" sx={{ fontWeight: 600, fontSize: "0.95rem" }}>
              {date}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {t("changes.thatDay", { count: items.length })}
            </Typography>
          </Box>
          {items.map((change, i) => (
            <ChangeRow key={`${change.technology_id}-${i}`} change={change} onOpen={navigate} />
          ))}
        </Box>
      ))}
    </Box>
  );
}

/**
 * One chronicle row: which record, how the level changed and on what grounds.
 *
 * The level transition is set in a monospace face and stands right after the
 * name, because it is precisely the content of the row. For a new record the
 * former level is not shown at all: a dash in its place read as "it was zero".
 */
function ChangeRow({
  change, onOpen,
}: {
  change: RegistryChange;
  onOpen: (path: string) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const added = change.kind === "added";

  return (
    <Box sx={{ py: 0.75, borderBottom: 1, borderColor: "divider" }}>
      <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.5, flexWrap: "wrap" }}>
        {change.kind === "level_down" && (
          <Chip
            size="small"
            label={t("changes.levelDown")}
            sx={{ height: 20, color: "warning.main", borderColor: "warning.main" }}
            variant="outlined"
          />
        )}
        <MuiLink
          href={`/tech/${change.technology_id}`}
          onClick={(e) => { e.preventDefault(); onOpen(`/tech/${change.technology_id}`); }}
          sx={{ color: "text.primary", fontWeight: 600 }}
        >
          {change.name}
        </MuiLink>
        <Typography
          sx={{
            fontFamily: MONO, fontSize: "0.85rem",
            color: change.kind === "level_down" ? "warning.main" : "text.primary",
          }}
        >
          {added
            ? t("changes.appearedAt", { level: change.level_after })
            : `${change.level_before} → ${change.level_after}`}
        </Typography>

        {change.evidence.length > 0 && (
          <MuiLink
            component="button"
            onClick={() => setOpen((v) => !v)}
            sx={{ ml: "auto", fontSize: "0.75rem" }}
          >
            {open
              ? t("changes.hideBasis")
              : t("changes.basisCount", { count: change.evidence.length })}
          </MuiLink>
        )}
      </Box>

      <Collapse in={open}>
        <Box sx={{ mt: 0.75, pl: 1.5, borderLeft: 2, borderColor: "divider" }}>
          {change.evidence.map((e, j) => (
            <Typography key={j} variant="caption" sx={{ display: "block", color: "text.secondary" }}>
              {e.type}
              {e.source && (
                <>
                  {" · "}
                  <MuiLink href={e.source} target="_blank" rel="noopener">
                    {/*
                      The name of the source is shown rather than the whole
                      address. `openalex.org/W4400373146` tells a reader nothing
                      beyond `openalex.org` and takes four times the room.
                    */}
                    {hostOf(e.source)}
                  </MuiLink>
                </>
              )}
            </Typography>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url.replace(/^https?:\/\//, "").split("/")[0];
  }
}
