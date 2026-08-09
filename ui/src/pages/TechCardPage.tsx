import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Box, Typography, Paper, Chip, Alert, CircularProgress, Divider, Link as MuiLink,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { getRegistry } from "../api/client";
import { getTechProse } from "../i18n/index";
import { LevelBadge } from "../components/LevelBadge";
import { ConfigGlyph } from "../components/ConfigGlyph";
import { StratumChip } from "../components/StratumChip";
import type { RegistryTechnology } from "../api/types";

/**
 * Карточка технологии.
 *
 * Факты приходят из реестра, тексты — из ресурсов локализации по `prose_id`
 * (принцип K3). Рубрика «задача, барьеры, решения» применяется ко всем записям,
 * у которых такой текст есть, а не только к тем, что попали в прежнюю статью о
 * парадигмах.
 */
export function TechCardPage() {
  const { id } = useParams<{ id: string }>();
  const { t, i18n } = useTranslation();
  const [tech, setTech] = useState<RegistryTechnology | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    // Реестр приходит одним артефактом; нужная запись отбирается на клиенте.
    getRegistry()
      .then((res) => {
        const found = res.technologies.find((x) => x.id === id) ?? null;
        setTech(found);
        setError(found ? null : t("techCard.notFound"));
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [id, t]);

  if (loading) return <CircularProgress sx={{ display: "block", mx: "auto", my: 8 }} />;
  if (error) return <Alert severity="info" sx={{ m: 2 }}>{error}</Alert>;
  if (!tech) return null;

  const prose = getTechProse(tech.prose_id, i18n.language);

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 1 }}>
        <ConfigGlyph configuration={tech.configuration} size={32} />
        <Typography variant="h3" sx={{ flexGrow: 1, minWidth: 0 }}>{tech.name}</Typography>
        <LevelBadge
          level={tech.level}
          confidence={tech.confidence}
          manual={tech.evidence_basis === "manual"}
        />
      </Box>
      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", alignItems: "center", mb: 2 }}>
        <Chip size="small" label={t(`kind.${tech.kind}`, { defaultValue: tech.kind })} variant="outlined" />
        {tech.first_published && (
          <Chip size="small" variant="outlined" label={tech.first_published} />
        )}
        {tech.groups.map((g) => <StratumChip key={g} stratum={g} withName />)}
      </Box>

      {tech.links.length > 0 && (
        <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap", mb: 2 }}>
          {tech.links.map((link, i) => (
            <MuiLink key={i} href={link.url} target="_blank" rel="noopener" variant="body2">
              {link.label ?? link.url.replace(/^https?:\/\//, "").slice(0, 42)}
            </MuiLink>
          ))}
        </Box>
      )}

      {tech.core_idea && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="body2">{tech.core_idea}</Typography>
        </Paper>
      )}

      {prose.full && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="body2" sx={{ lineHeight: 1.75 }}>{prose.full}</Typography>
        </Paper>
      )}

      {(prose.problem || prose.barriers || prose.solutions) && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          {([
            ["techCard.problem", prose.problem],
            ["techCard.barriers", prose.barriers],
            ["techCard.solutions", prose.solutions],
          ] as const).map(([key, text]) => text ? (
            <Box key={key} sx={{ mb: 1.5 }}>
              <Typography variant="subtitle2" sx={{ mb: 0.5 }}>{t(key)}</Typography>
              <Typography variant="body2" sx={{ lineHeight: 1.75 }}>{text}</Typography>
            </Box>
          ) : null)}
        </Paper>
      )}

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>{t("techCard.groups")}</Typography>
        <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap" }}>
          {tech.groups.map((g) => (
            <Chip key={g} size="small" label={g} />
          ))}
          {tech.groups.length === 0 && <Typography variant="body2" color="text.secondary">—</Typography>}
        </Box>
      </Paper>

      {Object.keys(tech.configuration).length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>{t("techCard.configuration")}</Typography>
          {/*
            Без этой строки читатель не может отличить значение, сверенное с
            первоисточником, от значения по умолчанию, которое никто не смотрел.
            Выглядят они одинаково, а утверждают разное.
          */}
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
            {tech.configuration_reviewed
              ? t("techCard.configurationReviewed", { date: tech.configuration_reviewed })
              : t("techCard.configurationUnreviewed")}
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t("techCard.dimension")}</TableCell>
                  <TableCell>{t("techCard.value")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {Object.entries(tech.configuration).map(([dim, val]) => (
                  <TableRow key={dim}>
                    <TableCell sx={{ fontFamily: "monospace" }}>{dim}</TableCell>
                    <TableCell sx={{ fontFamily: "monospace" }}>{val}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {tech.residual.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>{t("techCard.residual")}</Typography>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {tech.residual.map((r, i) => <li key={i}><Typography variant="body2">{r}</Typography></li>)}
          </ul>
        </Paper>
      )}

      {tech.aliases.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>{t("techCard.aliases")}</Typography>
          <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap" }}>
            {tech.aliases.map((a) => <Chip key={a} size="small" label={a} variant="outlined" />)}
          </Box>
        </Paper>
      )}

      <Divider sx={{ my: 2 }} />

      {/* Почему такой уровень: вывод правила и свидетельства, на которых он стоит.
          Уровень без этого раздела — утверждение, которое нечем проверить. */}
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>{t("techCard.whyLevel")}</Typography>

        {!tech.level_reason && (
          <Typography variant="body2" color="text.secondary">
            {t("techCard.noEvidence")}
          </Typography>
        )}

        {tech.level_reason && (
          <>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 1.5 }}>
              <LevelBadge
                level={tech.level}
                confidence={tech.confidence}
                manual={tech.evidence_basis === "manual"}
              />
              <Typography variant="body2" color="text.secondary">
                {t("techCard.satisfied")}: {tech.level_reason.satisfied.join(", ")}
              </Typography>
            </Box>

            {(() => {
              // Невыполненные уровни делятся на два разных случая. Те, что выше
              // текущего, — это дорога вперёд. Те, что ниже, означают обход:
              // уровень достигнут другим путём, и это стоит объяснить, иначе
              // читатель сочтёт пропуск ошибкой.
              const order = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"];
              const current = tech.level ? order.indexOf(tech.level) : -1;
              const ahead = tech.level_reason!.missing.filter(
                (lv) => order.indexOf(lv) > current
              );
              const skipped = tech.level_reason!.missing.filter(
                (lv) => order.indexOf(lv) < current
              );
              return (
                <>
                  {ahead.length > 0 && (
                    <Box sx={{ mb: 1.5 }}>
                      <Typography variant="subtitle2" sx={{ mb: 0.25 }}>
                        {t("techCard.nextLevel")}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {t(`levelCondition.${ahead[0]}`, { defaultValue: ahead[0] })}
                      </Typography>
                    </Box>
                  )}
                  {skipped.length > 0 && (
                    <Box sx={{ mb: 1.5 }}>
                      <Typography variant="subtitle2" sx={{ mb: 0.25 }}>
                        {t("techCard.skipped")}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {t("techCard.skippedText", { levels: skipped.join(", ") })}
                      </Typography>
                    </Box>
                  )}
                </>
              );
            })()}

            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              {t("techCard.evidence")} ({tech.evidence.length})
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableBody>
                  {tech.evidence.map((e, i) => (
                    <TableRow key={i}>
                      <TableCell sx={{ fontFamily: "monospace", width: 170 }}>
                        {e.type}
                      </TableCell>
                      <TableCell>
                        {e.value}
                        {e.obtained_by === "manual" && (
                          <Chip
                            size="small" variant="outlined" sx={{ ml: 1 }}
                            label={t("techCard.manualShort")}
                          />
                        )}
                      </TableCell>
                      <TableCell sx={{ width: 220 }}>
                        <MuiLink href={e.source} target="_blank" rel="noopener">
                          {e.source.replace(/^https?:\/\//, "").slice(0, 34)}
                        </MuiLink>
                      </TableCell>
                      <TableCell className="tabular" sx={{ width: 100 }}>
                        {e.fetched_at}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </>
        )}
      </Paper>

      {tech.prose_id && (
        <Typography variant="caption" color="text.secondary">
          {t("techCard.proseId")}: <code>{tech.prose_id}</code>
        </Typography>
      )}

      <Box sx={{ mt: 2 }}>
        <MuiLink href="/registry">{t("techCard.backToRegistry")}</MuiLink>
      </Box>
    </Box>
  );
}
