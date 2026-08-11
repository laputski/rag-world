import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Box, Typography, Paper, Chip, Alert, CircularProgress, Collapse, Divider, Link as MuiLink,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { getRegistry } from "../api/client";
import { getTechProse } from "../i18n/index";
import { LevelBadge } from "../components/LevelBadge";
import { ConfigGlyph } from "../components/ConfigGlyph";
import { StratumChip } from "../components/StratumChip";
import type { ParseNote, RegistryTechnology } from "../api/types";

/**
 * Обоснование одного решения разбора конфигурации.
 *
 * Показывается свёрнутым: читателю, которому нужно значение, обоснование
 * мешает; читателю, который значению не верит, оно необходимо. Разворот — один
 * щелчок, и он не уводит со страницы.
 *
 * «Что делает система» и «почему из этого следует значение» разнесены
 * намеренно: первое проверяется по источнику, второе — по схеме измерений.
 */
function ParseNoteBlock({ note }: { note: ParseNote }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  return (
    <Box sx={{ mt: 0.5, fontFamily: "body" }}>
      <MuiLink
        component="button"
        onClick={() => setOpen((v) => !v)}
        sx={{ fontSize: "0.75rem", fontFamily: "inherit" }}
      >
        {open ? t("techCard.hideBasis") : t("techCard.showBasis")}
        {note.question && ` · ${t("techCard.readingOpen")}`}
      </MuiLink>
      <Collapse in={open}>
        <Box sx={{ mt: 1, pl: 1.5, borderLeft: 2, borderColor: "divider", maxWidth: "62ch" }}>
          <NoteLine label={t("techCard.basisDid")} text={note.did} />
          <NoteLine label={t("techCard.basisWhy")} text={note.why} />
          {note.instead && <NoteLine label={t("techCard.basisInstead")} text={note.instead} />}
          {note.question && (
            <NoteLine label={t("techCard.basisQuestion")} text={note.question} accent />
          )}
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
            {note.source}
          </Typography>
        </Box>
      </Collapse>
    </Box>
  );
}

function NoteLine({ label, text, accent }: { label: string; text: string; accent?: boolean }) {
  return (
    <Box sx={{ mb: 1 }}>
      <Typography
        variant="caption"
        sx={{
          display: "block",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          fontSize: "0.62rem",
          color: accent ? "warning.main" : "text.secondary",
        }}
      >
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontFamily: "body" }}>{text}</Typography>
    </Box>
  );
}

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

      {/*
        Краткая суть берётся из локализованной прозы, а не из поля реестра:
        поле хранит русский текст, и на английской версии он был бы русским
        абзацем посреди страницы. Поле остаётся запасным вариантом — у записи
        может не быть прозы, и тогда лучше показать русскую строку, чем ничего.
      */}
      {(prose.short || tech.core_idea) && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="body2">{prose.short ?? tech.core_idea}</Typography>
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
                {/*
                  Три разных утверждения об измерении показываются по-разному.
                  Переменное значение выбирается системой во время работы, и
                  без пометки читатель принял бы записанное за единственное.
                  Неприменимое измерение значения не имеет вовсе — строка
                  остаётся, потому что её отсутствие читалось бы как «забыли».
                */}
                {Object.entries(tech.configuration).map(([dim, val]) => {
                  const variable = tech.configuration_variable.includes(dim);
                  const note = tech.parse_notes.find((n) => n.code === dim);
                  return (
                    <TableRow key={dim} sx={{ "& > td": { borderBottom: note ? 0 : undefined } }}>
                      <TableCell sx={{ fontFamily: "monospace", verticalAlign: "top" }}>{dim}</TableCell>
                      <TableCell sx={{ fontFamily: "monospace" }}>
                        {val}
                        {variable && (
                          <Typography
                            component="span"
                            variant="caption"
                            color="text.secondary"
                            sx={{ ml: 1, fontFamily: "inherit" }}
                          >
                            {t("techCard.dimensionVariable")}
                          </Typography>
                        )}
                        {/*
                          Обоснование прямо под значением, а не в сноске.
                          Конфигурация — единственное место портала, где решение
                          принял человек: у уровня показан вывод правила, у
                          свидетельства — источник, и только здесь значение
                          появлялось без основания.
                        */}
                        {note && <ParseNoteBlock note={note} />}
                      </TableCell>
                    </TableRow>
                  );
                })}
                {tech.configuration_inapplicable.map((dim) => (
                  <TableRow key={dim}>
                    <TableCell sx={{ fontFamily: "monospace", opacity: 0.6 }}>{dim}</TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {t("techCard.dimensionInapplicable")}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          {(tech.configuration_variable.length > 0 ||
            tech.configuration_inapplicable.length > 0) && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: "block", mt: 1 }}
            >
              {tech.configuration_variable.length > 0 && t("techCard.variableNote")}
              {tech.configuration_variable.length > 0 &&
                tech.configuration_inapplicable.length > 0 && " "}
              {tech.configuration_inapplicable.length > 0 && t("techCard.inapplicableNote")}
            </Typography>
          )}
        </Paper>
      )}

      {tech.residual.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>{t("techCard.residual")}</Typography>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {(i18n.language === "en" ? tech.residual_en : tech.residual)
              .map((r, i) => <li key={i}><Typography variant="body2">{r}</Typography></li>)}
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
