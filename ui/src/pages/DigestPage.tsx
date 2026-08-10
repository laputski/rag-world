import { useEffect, useState } from "react";
import {
  Alert, Box, Chip, CircularProgress, Collapse, Divider, Link as MuiLink, Paper, Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { getDigest } from "../api/client";
import type { DigestIssue } from "../api/types";
import { MONO } from "../theme";

/**
 * Выпуски дайджеста.
 *
 * Дайджест выносит изменения наружу: портал знает, что произошло, но узнать об
 * этом можно, только зайдя на него.
 *
 * Текст выпуска порождается шаблоном по данным реестра, без языковой модели, и
 * это сказано читателю прямо. Различие существенно: портал стоит на том, что
 * каждое его утверждение проверяемо, а порождённый моделью текст читался бы как
 * утверждение портала, не будучи проверенным. Поэтому под текстом выпуска стоят
 * те самые записи и числа, из которых он собран, — читатель может пройти по
 * ссылкам и убедиться.
 */

function LevelMove({ move, onOpen }: {
  move: { technology_id: string; name: string; level_before: string | null; level_after: string };
  onOpen: (id: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <Box sx={{ display: "flex", alignItems: "baseline", gap: 1, py: 0.4 }}>
      <MuiLink
        component="button"
        onClick={() => onOpen(move.technology_id)}
        sx={{ textAlign: "left" }}
      >
        {move.name}
      </MuiLink>
      <Typography variant="caption" sx={{ color: "text.secondary" }}>
        {move.level_before
          ? t("digest.moved", { from: move.level_before, to: move.level_after })
          : t("digest.first", { level: move.level_after })}
      </Typography>
    </Box>
  );
}

/**
 * Основание выпуска: записи, изменение которых он пересказывает.
 *
 * Свёрнуто по умолчанию. Выпуск за неделю умещается в абзац, а список записей
 * за ним может быть на полсотни строк, и тогда сообщение тонет в собственном
 * доказательстве.
 */
function BasisList({ issue, onOpen }: {
  issue: DigestIssue;
  onOpen: (id: string) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const total = issue.added.length + issue.promoted.length + issue.demoted.length;

  return (
    <Box>
      <MuiLink
        component="button"
        onClick={() => setOpen((v) => !v)}
        sx={{ fontSize: "0.82rem" }}
      >
        {open ? t("digest.hideBasis") : t("digest.showBasis", { count: total })}
      </MuiLink>
      <Collapse in={open}>
        <Box sx={{ mt: 1.5, pl: 1.5, borderLeft: 2, borderColor: "divider" }}>
          {issue.demoted.map((m) => (
            <LevelMove key={`d-${m.technology_id}`} move={m} onOpen={onOpen} />
          ))}
          {issue.promoted.map((m) => (
            <LevelMove key={`p-${m.technology_id}`} move={m} onOpen={onOpen} />
          ))}
          {issue.added.map((m) => (
            <LevelMove key={`a-${m.technology_id}`} move={m} onOpen={onOpen} />
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}

export function DigestPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [issues, setIssues] = useState<DigestIssue[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDigest()
      .then((res) => { setIssues(res.issues); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Box sx={{ p: 4 }}><CircularProgress size={24} /></Box>;
  if (error) return <Box sx={{ p: 4 }}><Alert severity="error">{error}</Alert></Box>;

  return (
    <Box sx={{ maxWidth: 860, mx: "auto", px: 3, py: 4 }}>
      <Typography variant="h4" sx={{ mb: 1 }}>{t("digest.title")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1, maxWidth: "62ch" }}>
        {t("digest.subtitle")}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4, maxWidth: "62ch" }}>
        {t("digest.provenance")}
      </Typography>

      {issues.length === 0 && (
        <Alert severity="info">{t("digest.empty")}</Alert>
      )}

      {issues.map((issue) => (
        <Paper key={issue.issued_at} variant="outlined" sx={{ p: 3, mb: 2 }}>
          <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.5, mb: 1.5 }}>
            <Typography variant="h6" sx={{ fontFamily: MONO }}>{issue.issued_at}</Typography>
            <Typography variant="caption" color="text.secondary">
              {issue.since
                ? t("digest.period", { since: issue.since })
                : t("digest.firstIssue")}
            </Typography>
          </Box>

          <Typography variant="body1" sx={{ mb: 2 }}>{issue.text}</Typography>

          {(issue.added.length > 0 || issue.promoted.length > 0 || issue.demoted.length > 0) && (
            <>
              <Divider sx={{ my: 2 }} />
              {/*
                Под пересказом лежит то, из чего он собран, но свёрнутым:
                читателю выпуска нужен сам выпуск, а список из полусотни записей
                вытесняет его с экрана. Тому, кто хочет проверить, разворот
                стоит одного щелчка и со страницы не уводит.
              */}
              <BasisList
                issue={issue}
                onOpen={(id) => navigate(`/tech/${id}`)}
              />
            </>
          )}

          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mt: 2 }}>
            {issue.evidence_added > 0 && (
              <Chip size="small" variant="outlined"
                    label={t("digest.evidenceChip", { count: issue.evidence_added })} />
            )}
            {issue.links_checked > 0 && (
              <Chip size="small" variant="outlined"
                    label={t("digest.linksChip", { count: issue.links_checked })} />
            )}
            {issue.links_broken > 0 && (
              <Chip size="small" color="warning" variant="outlined"
                    label={t("digest.brokenChip", { count: issue.links_broken })} />
            )}
          </Box>
        </Paper>
      ))}
    </Box>
  );
}
