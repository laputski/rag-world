import { useEffect, useState } from "react";
import {
  Alert, Box, Chip, CircularProgress, Link as MuiLink, Paper, Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { getCandidates, getResiduals } from "../api/client";
import type { Candidate, ResidualMechanism } from "../api/types";
import { MONO } from "../theme";

/**
 * Пробелы портала: чего он о себе знает.
 *
 * Две очереди на одной странице, и они отвечают на разные вопросы. Остатки
 * говорят о **модели**: какие механизмы схема измерений не выражает у записей,
 * которые уже разобраны. Кандидаты говорят о **реестре**: какие работы, быть
 * может, следует в него завести. Первая измеряет полноту описания, вторая
 * полноту состава, и слитые в один список они смешали бы два разных
 * утверждения.
 *
 * Вместе они держатся потому, что обе показывают предел портала, и обе малы:
 * восемь механизмов и несколько работ в неделю не стоят отдельной страницы
 * каждая.
 */
export function ResidualsPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [rows, setRows] = useState<ResidualMechanism[]>([]);
  const [candidateRows, setCandidateRows] = useState<Candidate[]>([]);
  const [threshold, setThreshold] = useState(3);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getResiduals()
      .then((res) => {
        setRows(res.mechanisms);
        setThreshold(res.candidate_threshold);
        setError(null);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  // Очередь кандидатов необязательна: артефакта может не быть, если
  // обнаружение ещё не запускали. Её отсутствие страницу не ломает.
  useEffect(() => {
    getCandidates()
      .then((res) => setCandidateRows(res.candidates))
      .catch(() => setCandidateRows([]));
  }, []);

  if (loading) return <Box sx={{ p: 4 }}><CircularProgress size={24} /></Box>;
  if (error) return <Box sx={{ p: 4 }}><Alert severity="error">{error}</Alert></Box>;

  const candidates = rows.filter((r) => r.candidate);

  return (
    <Box sx={{ maxWidth: 860, mx: "auto", px: 3, py: 4 }}>
      <Typography variant="h4" sx={{ mb: 1 }}>{t("gaps.title")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4, maxWidth: "64ch" }}>
        {t("gaps.subtitle")}
      </Typography>

      <Typography variant="h5" sx={{ mb: 1 }}>{t("residuals.title")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1, maxWidth: "64ch" }}>
        {t("residuals.subtitle")}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4, maxWidth: "64ch" }}>
        {t("residuals.rule", { threshold })}
      </Typography>

      {candidates.length > 0 && (
        <Alert severity="info" sx={{ mb: 3 }}>
          {t("residuals.candidatesFound", { count: candidates.length })}
        </Alert>
      )}

      {rows.map((row) => (
        <Paper
          key={row.id}
          variant="outlined"
          sx={{
            p: 2.5, mb: 1.5,
            borderLeft: 3,
            borderLeftColor: row.candidate ? "warning.main" : "divider",
          }}
        >
          <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.5, flexWrap: "wrap", mb: 1 }}>
            <Typography variant="h6" sx={{ fontSize: "1.05rem" }}>
              {i18n.language === "en" ? row.term_en : row.term}
            </Typography>
            <Chip
              size="small"
              variant="outlined"
              color={row.candidate ? "warning" : "default"}
              label={t("residuals.mentions", { count: row.count })}
            />
            {row.candidate && (
              <Typography variant="caption" color="warning.main">
                {t("residuals.candidate")}
              </Typography>
            )}
          </Box>

          {row.note && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, maxWidth: "64ch" }}>
              {i18n.language === "en" ? row.note_en : row.note}
            </Typography>
          )}

          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", alignItems: "center" }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontFamily: MONO }}>
              {t("residuals.seenIn")}
            </Typography>
            {row.technologies.map((tech) => (
              <MuiLink
                key={tech.id}
                component="button"
                onClick={() => navigate(`/tech/${tech.id}`)}
                variant="body2"
              >
                {tech.name}
              </MuiLink>
            ))}
          </Box>
        </Paper>
      ))}

      {rows.length === 0 && <Alert severity="info">{t("residuals.empty")}</Alert>}

      {/*
        Вторая очередь: что, возможно, следует завести в реестр. Обнаружение
        записей не заводит, поэтому здесь предположения, а не технологии, и
        решение по каждому принимает человек.
      */}
      <Typography variant="h5" sx={{ mt: 5, mb: 1 }}>{t("candidates.title")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3, maxWidth: "64ch" }}>
        {t("candidates.subtitle")}
      </Typography>

      {candidateRows.length === 0 && (
        <Alert severity="info">{t("candidates.empty")}</Alert>
      )}

      {candidateRows.map((row) => (
        <Paper key={row.arxiv_id} variant="outlined" sx={{ p: 2.5, mb: 1.5 }}>
          <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.5, flexWrap: "wrap" }}>
            <MuiLink
              href={`https://arxiv.org/abs/${row.arxiv_id}`}
              target="_blank"
              rel="noopener"
              variant="body1"
            >
              {row.title}
            </MuiLink>
          </Box>
          <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap", mt: 0.75 }}>
            {row.published && (
              <Typography variant="caption" color="text.secondary" sx={{ fontFamily: MONO }}>
                {row.published.slice(0, 10)}
              </Typography>
            )}
            <Typography variant="caption" color="text.secondary" sx={{ fontFamily: MONO }}>
              arXiv:{row.arxiv_id}
            </Typography>
            {row.citations != null && (
              <Typography variant="caption" color="text.secondary">
                {t("candidates.citations", { count: row.citations })}
              </Typography>
            )}
          </Box>
        </Paper>
      ))}
    </Box>
  );
}
