import { useEffect, useState } from "react";
import { Box, Button, Link as MuiLink, Paper, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { getStats } from "../api/client";
import type { RegistryStats } from "../api/types";
import { toBibTeX, toGost, toPlain } from "../citation";
import { MONO } from "../theme";

/**
 * О портале: как устроены данные и как они обновляются.
 *
 * Страница существует потому, что портал требует доверия к числам, а доверие
 * даётся не заявлением о строгости, а возможностью проверить: увидеть правило,
 * расписание сбора, перечень источников и скачать сами данные.
 */

const DATA_FILES = [
  { name: "registry.json", key: "about.fileRegistry" },
  { name: "map.json", key: "about.fileMap" },
  { name: "changes.json", key: "about.fileChanges" },
  { name: "stats.json", key: "about.fileStats" },
  { name: "feed.xml", key: "about.fileFeed" },
];

/** Источники, из которых сбор действительно идёт сегодня. */
const SOURCES = ["arXiv", "OpenAlex", "GitHub", "PyPI", "Papers with Code"];

interface Release { tag: string }

/** Готовая ссылка с кнопкой копирования. */
function Snippet({ text }: { text: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  return (
    <Box sx={{ mt: 1 }}>
      <Box component="pre" sx={{
        fontFamily: MONO, fontSize: "0.78rem", lineHeight: 1.6, m: 0,
        p: 1.5, bgcolor: "action.hover", borderRadius: 1,
        overflowX: "auto", whiteSpace: "pre-wrap",
      }}>
        {text}
      </Box>
      <Button size="small" sx={{ mt: 0.5 }} onClick={() => {
        navigator.clipboard?.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}>
        {copied ? t("cite.copied") : t("cite.copy")}
      </Button>
    </Box>
  );
}

export function AboutPage() {
  const { t, i18n } = useTranslation();
  // ГОСТ англоязычному читателю не нужен: это российский стандарт.
  const style = i18n.language === "ru" ? toGost : toPlain;
  const [stats, setStats] = useState<RegistryStats | null>(null);
  const [release, setRelease] = useState<string | null>(null);

  useEffect(() => { getStats().then(setStats).catch(() => setStats(null)); }, []);
  useEffect(() => {
    fetch("/data/releases/index.json")
      .then((r) => (r.ok ? r.json() : { releases: [] }))
      .then((d) => setRelease((d.releases as Release[])?.[0]?.tag ?? null))
      .catch(() => setRelease(null));
  }, []);

  return (
    <Box sx={{ maxWidth: 760 }}>
      <Typography variant="h2" sx={{ mb: 1 }}>{t("about.title")}</Typography>
      <Typography variant="body1" sx={{ mb: 3, lineHeight: 1.75 }}>
        {t("about.intro")}
      </Typography>

      <Typography variant="h5" sx={{ mb: 1 }}>{t("about.howLevels")}</Typography>
      <Typography variant="body1" sx={{ mb: 3, lineHeight: 1.75 }}>
        {t("about.howLevelsText")}
      </Typography>

      <Typography variant="h5" sx={{ mb: 1 }}>{t("about.howUpdates")}</Typography>
      <Typography variant="body1" sx={{ mb: 1.5, lineHeight: 1.75 }}>
        {t("about.howUpdatesText")}
      </Typography>
      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: 3 }}>
        {SOURCES.map((source) => (
          <Typography key={source} variant="caption" sx={{
            fontFamily: MONO, border: 1, borderColor: "divider", borderRadius: 1, px: 0.75, py: 0.25,
          }}>
            {source}
          </Typography>
        ))}
      </Box>

      <Typography variant="h5" sx={{ mb: 1 }}>{t("about.limits")}</Typography>
      <Typography variant="body1" sx={{ mb: 3, lineHeight: 1.75 }}>
        {t("about.limitsText")}
      </Typography>

      <Typography variant="h5" sx={{ mb: 1 }}>{t("about.data")}</Typography>
      <Typography variant="body1" sx={{ mb: 1.5, lineHeight: 1.75 }}>
        {t("about.dataText")}
      </Typography>
      <Box component="ul" sx={{ pl: 3, m: 0, mb: 3 }}>
        {DATA_FILES.map((file) => (
          <Box component="li" key={file.name} sx={{ mb: 0.5 }}>
            <MuiLink href={`/data/${file.name}`} download sx={{ fontFamily: MONO, fontSize: "0.85rem" }}>
              {file.name}
            </MuiLink>
            <Typography component="span" variant="body2" color="text.secondary">
              {" — "}{t(file.key)}
            </Typography>
          </Box>
        ))}
      </Box>

      {/*
        Ссылаться следует на выпуск: состояние записи меняется, и ссылка на
        текущее состояние подтвердит со временем не то, что подтверждала.
        Поэтому метка выпуска стоит в каждом примере.
      */}
      {release && (
        <>
          <Typography variant="h5" sx={{ mb: 1 }}>{t("about.cite")}</Typography>
          <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle2">{t("cite.gost")}</Typography>
            <Snippet text={style({ release })} />
          </Paper>
          <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle2">{t("cite.bibtex")}</Typography>
            <Snippet text={toBibTeX({ release })} />
          </Paper>
          <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
            <Typography variant="subtitle2">{t("cite.recordTitle")}</Typography>
            <Snippet text={style({
              release, technology: { id: "pathrag", name: "PathRAG" },
            })} />
          </Paper>
        </>
      )}

      {stats && (
        <>
          <Typography variant="h5" sx={{ mb: 1 }}>{t("about.state")}</Typography>
          <Box component="dl" sx={{ m: 0, display: "grid", gridTemplateColumns: "auto 1fr", gap: "6px 16px" }}>
            {[
              [t("about.stateTotal"), stats.total],
              [t("about.stateWithLevel"), stats.with_level],
              [t("about.stateWithAttention"), stats.with_attention],
              [t("about.stateEvidence"), stats.evidence_total],
              [t("about.stateFreshest"), stats.freshest_evidence ?? "—"],
            ].map(([label, value]) => (
              <Box key={String(label)} sx={{ display: "contents" }}>
                <Typography component="dt" variant="body2" color="text.secondary">{label}</Typography>
                <Typography component="dd" variant="body2" sx={{ fontFamily: MONO, m: 0 }}>{value}</Typography>
              </Box>
            ))}
          </Box>
        </>
      )}
    </Box>
  );
}
