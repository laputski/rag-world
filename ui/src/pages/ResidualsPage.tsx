import { useEffect, useState } from "react";
import {
  Alert, Box, Chip, CircularProgress, Link as MuiLink, Paper, Tab, Tabs, Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { getCandidates, getResiduals } from "../api/client";
import type { Candidate, ResidualMechanism } from "../api/types";
import { MONO } from "../theme";
import { useDocumentHead } from "../useDocumentHead";

//: The largest fitness score; it matches core/candidate_fit.py.
const FIT_MAX = 10;

/**
 * The gaps of the portal: what it knows about itself.
 *
 * Two queues on one page, and they answer different questions. The residuals
 * speak of the **model**: which mechanisms the dimension schema does not express
 * among the records already read. The candidates speak of the **registry**:
 * which records may need to be created in it. The first measures how complete
 * the description is and the second how complete the collection is, and merged
 * into one list they would mix two different claims.
 *
 * They live together because both show a limit of the portal, and eight
 * mechanisms and a few works a week do not warrant a page each.
 */
export function ResidualsPage() {

  const { t, i18n } = useTranslation();
  useDocumentHead({
    title: t("head.residuals.title"),
    description: t("head.residuals.description"),
  });
  const navigate = useNavigate();
  const [rows, setRows] = useState<ResidualMechanism[]>([]);
  const [candidateRows, setCandidateRows] = useState<Candidate[]>([]);
  const [threshold, setThreshold] = useState(3);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // Tabs rather than two sections in a row: the queues answer different
  // questions and a reader usually wants one of them. Eight mechanisms followed
  // by twenty works would force scrolling past what is not wanted.
  const [tab, setTab] = useState(0);

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

  // The candidate queue is optional: the artefact may be absent when discovery
  // has never been run. Its absence does not break the page.
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
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2, maxWidth: "64ch" }}>
        {t("gaps.subtitle")}
      </Typography>

      <Tabs
        value={tab}
        onChange={(_, value: number) => setTab(value)}
        sx={{ mb: 3, borderBottom: 1, borderColor: "divider" }}
      >
        <Tab label={`${t("residuals.title")} · ${rows.length}`} />
        <Tab label={`${t("candidates.title")} · ${candidateRows.length}`} />
      </Tabs>

      {tab === 0 && (
        <>
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
        </>
      )}

      {/*
        The second queue: what may need to be created in the registry.
        Discovery creates no records, so these are suppositions rather than
        technologies, and the verdict on each is a person's.
      */}
      {tab === 1 && (
        <>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1, maxWidth: "64ch" }}>
        {t("candidates.subtitle")}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3, maxWidth: "64ch" }}>
        {t("candidates.fitWhat")}
      </Typography>

      {candidateRows.length === 0 && (
        <Alert severity="info">{t("candidates.empty")}</Alert>
      )}

      {candidateRows.map((row) => (
        <Paper key={row.arxiv_id} variant="outlined" sx={{ p: 2.5, mb: 1.5 }}>
          <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.5, flexWrap: "wrap" }}>
            <Chip
              size="small"
              variant="outlined"
              color={row.fit.score >= 6 ? "primary" : "default"}
              label={t("candidates.fit", { score: row.fit.score, max: FIT_MAX })}
            />
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
          {/*
            The abstract is given as the authors wrote it: retelling it in other
            words would mean asserting something about a work the portal has not
            read yet.

            The terms of the score are always shown: a number without them says
            "take my word for it", and the portal is built on the opposite.
          */}
          <Box component="ul" sx={{ pl: 2.5, m: 0, mt: 1 }}>
            {row.fit.signals.map((signal, i) => (
              <Box component="li" key={i}>
                <Typography variant="caption" color="text.secondary">
                  {t(`candidates.signal.${signal.code}`, {
                    tasks: (signal.tasks ?? []).join(", "),
                    count: signal.count,
                  })}
                </Typography>
              </Box>
            ))}
          </Box>
          {row.abstract && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1, maxWidth: "70ch" }}>
              {row.abstract}
            </Typography>
          )}
        </Paper>
      ))}
        </>
      )}
    </Box>
  );
}
