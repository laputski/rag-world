import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import {
  Alert, Box, Chip, CircularProgress, Link as MuiLink, Tooltip, Typography,
} from "@mui/material";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { getChanges, getMaturityMap, getStats } from "../api/client";
import type { MaturityArtifact, RegistryChange, RegistryStats } from "../api/types";
/*
  The chart builder loads apart from the page.

  It weighs about a megabyte and is needed by two views only, while the rest of
  the front page is text: the summary, the chronicle, the legend. Without the
  split a reader waited a megabyte of code before seeing a single line. The room
  for the chart is held in advance, so the map appearing does not jolt the
  page.
*/
const MaturityMap = lazy(() =>
  import("../components/MaturityMap").then((m) => ({ default: m.MaturityMap })));
const MaturityGrid = lazy(() =>
  import("../components/MaturityGrid").then((m) => ({ default: m.MaturityGrid })));
import { LevelBadge } from "../components/LevelBadge";
import { MONO, stratumColor, type ThemeMode } from "../theme";
import { useTheme } from "@mui/material/styles";
import { useDocumentHead } from "../useDocumentHead";

/**
 * The front page: the state of the field at a glance.
 *
 * The order follows the questions a reader asks in turn: where things stand (the
 * map), what has changed (the chronicle strip), how much there is in all and how
 * much is covered (the summary). Long texts live in the article and on the
 * cards; their absence here is deliberate.
 */

type Projection = "map" | "grid";

export function HomePage() {

  const { t } = useTranslation();
  useDocumentHead({
    title: t("head.home.title"),
    description: t("head.home.description"),
  });
  const theme = useTheme();
  const navigate = useNavigate();
  const [artifact, setArtifact] = useState<MaturityArtifact | null>(null);
  const [stats, setStats] = useState<RegistryStats | null>(null);
  const [changes, setChanges] = useState<RegistryChange[]>([]);
  const [projection, setProjection] = useState<Projection>("map");
  const [movement, setMovement] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getMaturityMap(), getStats(), getChanges()])
      .then(([map, s, c]) => {
        setArtifact(map);
        setStats(s);
        setChanges(c.changes);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const levelBars = useMemo(() => {
    if (!stats) return [];
    const order = ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "unknown"];
    const max = Math.max(...Object.values(stats.by_level), 1);
    return order
      .filter((level) => stats.by_level[level] != null)
      .map((level) => ({
        level,
        count: stats.by_level[level],
        share: stats.by_level[level] / max,
      }));
  }, [stats]);

  /*
    The count of changes over a month. The window is the same one the chronicle
    page opens with by default, so the number here and the number there agree,
    and a reader who follows the link sees a continuation rather than a different
    picture.
  */
  const recent = useMemo(() => {
    const since = new Date();
    since.setDate(since.getDate() - 31);
    const within = changes.filter((c) => new Date(c.changed_at) >= since);
    const count = (kind: string) => within.filter((c) => c.kind === kind).length;
    const parts: { key: string; n: number }[] = [
      { key: "home.downCount", n: count("level_down") },
      { key: "home.upCount", n: count("level_up") },
      { key: "home.addedCount", n: count("added") },
    ];
    return {
      total: within.length,
      words: parts.filter((p) => p.n > 0).map((p) => t(p.key, { count: p.n })),
    };
  }, [changes, t]);

  if (error) {
    return <Alert severity="info">{t("map.unavailable")}</Alert>;
  }
  if (!artifact || !stats) {
    return <CircularProgress sx={{ display: "block", mx: "auto", my: 8 }} />;
  }

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "baseline", gap: 2, flexWrap: "wrap", mb: 0.5 }}>
        <Typography variant="h2">{t("map.title")}</Typography>
        <Tooltip title={t("map.howToRead")}>
          <InfoOutlinedIcon sx={{ fontSize: 18, color: "text.secondary", cursor: "help" }} />
        </Tooltip>
      </Box>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 2, maxWidth: 760 }}>
        {t("map.subtitle")}
      </Typography>

      {/* The data status strip: the build date and the staleness mark, always shown. */}
      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", alignItems: "center", mb: 1.5 }}>
        <Chip size="small" variant="outlined" label={
          `${t("common.builtAt")}: ${new Date(artifact.built_at).toLocaleDateString()}`
        } />
        <Chip size="small" variant="outlined" label={
          `${t("map.count")}: ${artifact.count}`
        } />
        <Chip size="small" variant="outlined" label={
          `${t("map.ruleVersion")}: ${artifact.rule_version}`
        } />
        {artifact.stale && <Chip size="small" color="warning" label={t("map.stale")} />}
      </Box>

      <Box
        sx={{
          display: "flex", gap: 2.5, alignItems: "center", flexWrap: "wrap",
          py: 1, borderTop: 1, borderBottom: 1, borderColor: "divider", mb: 1,
        }}
      >
        {(["map", "grid"] as Projection[]).map((p) => (
          <Typography
            key={p}
            onClick={() => setProjection(p)}
            sx={{
              fontSize: "0.85rem", cursor: "pointer",
              color: projection === p ? "text.primary" : "text.secondary",
              fontWeight: projection === p ? 600 : 400,
            }}
          >
            {t(`map.projection.${p}`)}
          </Typography>
        ))}
        {projection === "map" && (
          <Typography
            onClick={() => setMovement((m) => !m)}
            sx={{
              fontSize: "0.85rem", cursor: "pointer", ml: 1,
              color: movement ? "text.primary" : "text.secondary",
              fontWeight: movement ? 600 : 400,
            }}
          >
            {t("map.showMovement")}
          </Typography>
        )}
        <MuiLink href="/registry" sx={{ ml: "auto", fontSize: "0.85rem" }}>
          {t("map.openRegistry")}
        </MuiLink>
      </Box>

      <Suspense
        fallback={
          <Box
            sx={{
              height: 520, mb: 2, display: "flex",
              alignItems: "center", justifyContent: "center",
            }}
          >
            <CircularProgress />
          </Box>
        }
      >
        {projection === "map" ? (
          <MaturityMap
            artifact={artifact}
            showMovement={movement}
            onSelect={(id) => navigate(`/tech/${id}`)}
          />
        ) : (
          <MaturityGrid artifact={artifact} onSelect={(id) => navigate(`/tech/${id}`)} />
        )}
      </Suspense>

      {/* The stratum legend: colour always means a stratum and nothing else. */}
      <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap", mb: 3 }}>
        {artifact.strata.map((s) => (
          <Box key={s.code} sx={{ display: "flex", alignItems: "center", gap: 0.6 }}>
            <Box sx={{
              width: 9, height: 9, borderRadius: "2px",
              bgcolor: stratumColor(s.code, theme.palette.mode as ThemeMode),
            }} />
            <Typography variant="caption">
              {t(`stratum.${s.code}`, { defaultValue: s.name }).replace(/^[A-G]\.\s*/, "")}
            </Typography>
          </Box>
        ))}
      </Box>

      <Box sx={{ display: "flex", gap: 5, flexWrap: "wrap", alignItems: "flex-start" }}>
        {/*
          What has changed: freshness is proved by a change rather than by a
          date.

          The block is taken in at first glance and therefore begins with the
          counts — how much happened over a month, and whether a demotion was
          among it. Six rows used to lie here without dates and without the kind
          of change, and a new record was shown as "— → L1", so the dash read as
          a level. The details are reached by a link: the full chronicle is
          gathered by date and carries the grounds.
        */}
        <Box sx={{ flex: "1 1 380px", minWidth: 0 }}>
          <Typography variant="h6" sx={{ mb: 0.5 }}>{t("changes.title")}</Typography>

          {changes.length === 0 && (
            <Typography variant="body2" color="text.secondary">{t("changes.empty")}</Typography>
          )}

          {changes.length > 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              {recent.total === 0
                ? t("home.changesQuiet")
                : `${t("home.changesWindow")}: ${recent.words.join(", ")}.`}
            </Typography>
          )}

          {changes.slice(0, 6).map((change, i) => {
            const added = change.kind === "added";
            const down = change.kind === "level_down";
            return (
              <Box
                key={`${change.technology_id}-${i}`}
                sx={{
                  display: "flex", alignItems: "baseline", gap: 1.5, py: 0.9,
                  borderBottom: 1, borderColor: "divider",
                }}
              >
                <MuiLink
                  href={`/tech/${change.technology_id}`}
                  onClick={(e) => { e.preventDefault(); navigate(`/tech/${change.technology_id}`); }}
                  sx={{ color: "text.primary", fontSize: "0.9rem", minWidth: 0 }}
                >
                  {change.name}
                </MuiLink>
                {/*
                  A new record is described in words rather than by a dash and
                  an arrow: a dash in the place of a former level reads as a
                  level that does not exist, and it read exactly so in the
                  summary beside it.
                */}
                <Typography
                  variant="caption"
                  sx={{ fontFamily: MONO, color: down ? "warning.main" : "text.secondary" }}
                >
                  {added
                    ? t("changes.appearedAt", { level: change.level_after })
                    : `${change.level_before} → ${change.level_after}`}
                </Typography>
                <Typography
                  variant="caption" color="text.secondary" className="tabular"
                  sx={{ ml: "auto", flexShrink: 0 }}
                >
                  {change.changed_at.slice(5)}
                </Typography>
              </Box>
            );
          })}

          {changes.length > 0 && (
            <MuiLink href="/changes" sx={{ display: "inline-block", mt: 1, fontSize: "0.85rem" }}>
              {t("changes.all")}
            </MuiLink>
          )}
        </Box>

        {/* The summary: distribution and coverage. */}
        <Box sx={{ flex: "1 1 340px", minWidth: 0 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>{t("stats.title")}</Typography>
          {levelBars.map((bar) => (
            <Box key={bar.level} sx={{ display: "flex", alignItems: "center", gap: 1, py: 0.3 }}>
              {/*
                The row for "no level computed" stood as a dash and read as one
                more level of the scale, the more so because L6 fell out of the
                summary entirely. The scale is now shown whole, empty levels
                included, and what is uncounted is named in words.
              */}
              <Box sx={{ width: bar.level === "unknown" ? "auto" : 34, flexShrink: 0 }}>
                {bar.level === "unknown"
                  ? (
                    <Typography variant="caption" color="text.secondary">
                      {t("map.levelUnknown")}
                    </Typography>
                  )
                  : <LevelBadge level={bar.level} showScale={false} />}
              </Box>
              <Box sx={{ flexGrow: 1, height: 8, bgcolor: "action.hover", borderRadius: 0.5 }}>
                <Box sx={{
                  width: `${bar.share * 100}%`, height: "100%", borderRadius: 0.5,
                  bgcolor: bar.level === "unknown" ? "text.disabled" : "text.secondary",
                }} />
              </Box>
              <Typography variant="caption" className="tabular" sx={{ fontFamily: MONO, width: 24, textAlign: "right" }}>
                {bar.count}
              </Typography>
            </Box>
          ))}
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5, lineHeight: 1.7 }}>
            {t("stats.coverage", {
              withLevel: stats.with_level,
              total: stats.total,
              withAttention: stats.with_attention,
              evidence: stats.evidence_total,
            })}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
