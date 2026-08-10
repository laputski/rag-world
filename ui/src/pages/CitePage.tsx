import { useEffect, useState } from "react";
import { Alert, Box, Button, Paper, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { toBibTeX, toGost } from "../citation";
import { MONO } from "../theme";

/**
 * Как ссылаться на портал.
 *
 * Различие между ссылкой на текущее состояние и ссылкой на выпуск —
 * единственное, что здесь важно объяснить. Портал меняется: запись, на которую
 * сослались вчера, сегодня может иметь другой уровень, и ссылка на текущее
 * состояние подтвердит не то, что подтверждала. Такая ссылка хуже отсутствия
 * ссылки, потому что выглядит надёжной.
 */

interface Release {
  tag: string;
  released_at: string;
  technologies: number;
  evidence: number;
  reviewed: number;
}

function Snippet({ text }: { text: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  return (
    <Box sx={{ mt: 1 }}>
      <Box
        component="pre"
        sx={{
          fontFamily: MONO, fontSize: "0.78rem", lineHeight: 1.6, m: 0,
          p: 1.5, bgcolor: "action.hover", borderRadius: 1,
          overflowX: "auto", whiteSpace: "pre-wrap",
        }}
      >
        {text}
      </Box>
      <Button
        size="small"
        sx={{ mt: 0.5 }}
        onClick={() => {
          navigator.clipboard?.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        }}
      >
        {copied ? t("cite.copied") : t("cite.copy")}
      </Button>
    </Box>
  );
}

export function CitePage() {
  const { t } = useTranslation();
  const [releases, setReleases] = useState<Release[]>([]);

  useEffect(() => {
    fetch("/data/releases/index.json")
      .then((r) => (r.ok ? r.json() : { releases: [] }))
      .then((d) => setReleases(d.releases ?? []))
      .catch(() => setReleases([]));
  }, []);

  const latest = releases[0];

  return (
    <Box sx={{ maxWidth: 820, mx: "auto", px: 3, py: 4 }}>
      <Typography variant="h4" sx={{ mb: 1 }}>{t("cite.title")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3, maxWidth: "64ch" }}>
        {t("cite.intro")}
      </Typography>

      <Alert severity="warning" sx={{ mb: 3 }}>{t("cite.warning")}</Alert>

      {!latest && <Alert severity="info">{t("cite.noReleases")}</Alert>}

      {latest && (
        <>
          <Paper variant="outlined" sx={{ p: 2.5, mb: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              {t("cite.latest", { tag: latest.tag })}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t("cite.contents", {
                technologies: latest.technologies,
                evidence: latest.evidence,
                reviewed: latest.reviewed,
              })}
            </Typography>
          </Paper>

          <Paper variant="outlined" sx={{ p: 2.5, mb: 2 }}>
            <Typography variant="subtitle2">{t("cite.gost")}</Typography>
            <Snippet text={toGost({ release: latest.tag })} />
          </Paper>

          <Paper variant="outlined" sx={{ p: 2.5, mb: 2 }}>
            <Typography variant="subtitle2">{t("cite.bibtex")}</Typography>
            <Snippet text={toBibTeX({ release: latest.tag })} />
          </Paper>

          <Paper variant="outlined" sx={{ p: 2.5 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>{t("cite.recordTitle")}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1, maxWidth: "64ch" }}>
              {t("cite.recordBody")}
            </Typography>
            <Snippet
              text={toGost({
                release: latest.tag,
                technology: { id: "pathrag", name: "PathRAG" },
              })}
            />
          </Paper>
        </>
      )}
    </Box>
  );
}
