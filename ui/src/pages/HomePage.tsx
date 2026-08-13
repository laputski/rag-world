import { useEffect, useMemo, useState } from "react";
import {
  Alert, Box, Chip, CircularProgress, Link as MuiLink, Tooltip, Typography,
} from "@mui/material";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { getChanges, getMaturityMap, getStats } from "../api/client";
import type { MaturityArtifact, RegistryChange, RegistryStats } from "../api/types";
import { MaturityMap } from "../components/MaturityMap";
import { MaturityGrid } from "../components/MaturityGrid";
import { LevelBadge } from "../components/LevelBadge";
import { MONO, stratumColor, type ThemeMode } from "../theme";
import { useTheme } from "@mui/material/styles";
import { useDocumentHead } from "../useDocumentHead";

/**
 * Главная страница: состояние области с одного взгляда.
 *
 * Порядок продиктован вопросами, которые читатель задаёт по очереди: где что
 * находится (карта), что изменилось (полоса хроники), сколько всего и насколько
 * покрыто (сводка). Длинные тексты живут в статье и карточках; здесь их нет
 * намеренно.
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

      {/* Полоса состояния данных: дата сборки и признак устаревания видны всегда. */}
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

      {projection === "map" ? (
        <MaturityMap
          artifact={artifact}
          showMovement={movement}
          onSelect={(id) => navigate(`/tech/${id}`)}
        />
      ) : (
        <MaturityGrid artifact={artifact} onSelect={(id) => navigate(`/tech/${id}`)} />
      )}

      {/* Легенда стратов: цвет всегда означает страту и ничего больше. */}
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
        {/* Что изменилось: свежесть доказывается изменением, а не датой. */}
        <Box sx={{ flex: "1 1 380px", minWidth: 0 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>{t("changes.title")}</Typography>
          {changes.length === 0 && (
            <Typography variant="body2" color="text.secondary">{t("changes.empty")}</Typography>
          )}
          {changes.slice(0, 6).map((change, i) => (
            <Box
              key={`${change.technology_id}-${i}`}
              sx={{
                display: "flex", alignItems: "center", gap: 1.5, py: 0.9,
                borderBottom: 1, borderColor: "divider",
              }}
            >
              <MuiLink
                href={`/tech/${change.technology_id}`}
                onClick={(e) => { e.preventDefault(); navigate(`/tech/${change.technology_id}`); }}
                sx={{ color: "text.primary", fontSize: "0.9rem", flexGrow: 1, minWidth: 0 }}
              >
                {change.name}
              </MuiLink>
              <Typography variant="caption" sx={{ fontFamily: MONO }}>
                {change.level_before ?? "—"} → {change.level_after}
              </Typography>
            </Box>
          ))}
          {changes.length > 0 && (
            <MuiLink href="/changes" sx={{ display: "inline-block", mt: 1, fontSize: "0.85rem" }}>
              {t("changes.all")}
            </MuiLink>
          )}
        </Box>

        {/* Сводка: распределение и покрытие. */}
        <Box sx={{ flex: "1 1 340px", minWidth: 0 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>{t("stats.title")}</Typography>
          {levelBars.map((bar) => (
            <Box key={bar.level} sx={{ display: "flex", alignItems: "center", gap: 1, py: 0.3 }}>
              <Box sx={{ width: 34 }}>
                {bar.level === "unknown"
                  ? <Typography variant="caption" sx={{ fontFamily: MONO }}>—</Typography>
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
