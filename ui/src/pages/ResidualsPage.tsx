import { useEffect, useState } from "react";
import {
  Alert, Box, Chip, CircularProgress, Link as MuiLink, Paper, Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { getResiduals } from "../api/client";
import type { ResidualMechanism } from "../api/types";
import { MONO } from "../theme";

/**
 * Очередь остатков: чего схема измерений не выражает.
 *
 * Схема должна расти от наблюдений, а не от воображения. Механизм, который
 * приходится записывать в остаток снова и снова, показывает место, где схема
 * мала; встреченный однажды — частность одной работы, и измерения он не стоит.
 *
 * Страница существует ещё и затем, чтобы предел схемы был виден читателю. Без
 * неё портал утверждал бы полноту, которой у него нет: двадцать шесть измерений
 * описывают многое, но не всё, и честнее показать, что именно не описывают.
 */
export function ResidualsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [rows, setRows] = useState<ResidualMechanism[]>([]);
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

  if (loading) return <Box sx={{ p: 4 }}><CircularProgress size={24} /></Box>;
  if (error) return <Box sx={{ p: 4 }}><Alert severity="error">{error}</Alert></Box>;

  const candidates = rows.filter((r) => r.candidate);

  return (
    <Box sx={{ maxWidth: 860, mx: "auto", px: 3, py: 4 }}>
      <Typography variant="h4" sx={{ mb: 1 }}>{t("residuals.title")}</Typography>
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
            <Typography variant="h6" sx={{ fontSize: "1.05rem" }}>{row.term}</Typography>
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
              {row.note}
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
    </Box>
  );
}
