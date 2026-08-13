import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Box, Typography, Paper, Chip, Alert, CircularProgress, Collapse, Divider, Link as MuiLink,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tooltip,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { getRegistry } from "../api/client";
import { getTechProse, getDimensionLabel, getValueLabel } from "../i18n/index";
import { LevelBadge } from "../components/LevelBadge";
import { ConfigGlyph } from "../components/ConfigGlyph";
import { ConfigFlow } from "../components/ConfigFlow";
import { StratumChip } from "../components/StratumChip";
import { DIMENSIONS, STRATA } from "../schema.generated";
import type { ParseNote, RegistryTechnology } from "../api/types";

/**
 * Проза карточки: абзацы, а не полотно.
 *
 * Тексты хранятся с пустой строкой между абзацами, как в любом обычном
 * источнике. Без этой разбивки описание в четыреста слов выходит одним
 * блоком, который читатель пролистывает не читая.
 */
function Prose({ text }: { text: string }) {
  const paragraphs = text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  return (
    <>
      {paragraphs.map((p, i) => (
        <Typography
          key={i}
          variant="body2"
          sx={{ lineHeight: 1.75, mb: i < paragraphs.length - 1 ? 1.5 : 0 }}
        >
          {p}
        </Typography>
      ))}
    </>
  );
}

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
/**
 * Обоснование разбора: почему у измерения такое значение.
 *
 * Перевод идёт записями и хранится рядом с оригиналом, как в словаре остатков:
 * обоснование бессмысленно в отрыве от измерения, к которому относится. Пока
 * запись не переведена, показывается русский текст с пометкой об этом: пустое
 * место и молчаливый русский абзац одинаково выглядят поломкой.
 */
function ParseNoteBlock({ note }: { note: ParseNote }) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);

  // Перевод обоснований идёт записями, и пока он не закончен, часть карточек
  // остаётся русской. Читателю об этом сказано прямо на тех карточках, где так
  // и есть: пустое место либо молчаливый русский абзац хуже, чем пометка.
  const english = i18n.language !== "ru";
  const translated = !english || Boolean(note.did_en && note.why_en);
  const pick = (ru: string, en?: string) => (english && en ? en : ru);

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
        {/*
          Пометка `data-basis` называет единственное место карточки, где на
          английской версии законно стоит русский текст. По ней же проверка
          отличает намеренное от забытого перевода.
        */}
        <Box
          data-basis="ru"
          sx={{ mt: 1, pl: 1.5, borderLeft: 2, borderColor: "divider", maxWidth: "62ch" }}
        >
          {!translated && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: "block", mb: 1, fontStyle: "italic" }}
            >
              {t("techCard.basisNotYetTranslated")}
            </Typography>
          )}
          <NoteLine label={t("techCard.basisDid")} text={pick(note.did, note.did_en)} />
          <NoteLine label={t("techCard.basisWhy")} text={pick(note.why, note.why_en)} />
          {note.instead && (
            <NoteLine
              label={t("techCard.basisInstead")}
              text={pick(note.instead, note.instead_en)}
            />
          )}
          {note.question && (
            <NoteLine
              label={t("techCard.basisQuestion")}
              text={pick(note.question, note.question_en)}
              accent
            />
          )}
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
            {pick(note.source, note.source_en)}
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

      {/*
        Источник, который портал не смог открыть сам, помечается прямо здесь.
        Портал стоит на том, что каждое его утверждение проверяемо, и «ссылки
        проверены еженедельно» — тоже утверждение. У трёх адресов оно неверно:
        издательства отвечают роботу отказом по правам, и подтвердить их может
        только человек. Умолчать значило бы выдать непроверенное за
        проверенное.
      */}
      {tech.links.length > 0 && (
        <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap", mb: 2 }}>
          {tech.links.map((link, i) => (
            <Box key={i} sx={{ display: "flex", alignItems: "baseline", gap: 0.5 }}>
              <MuiLink href={link.url} target="_blank" rel="noopener" variant="body2">
                {link.label ?? link.url.replace(/^https?:\/\//, "").slice(0, 42)}
              </MuiLink>
              {link.status === "guarded" && (
                <Tooltip title={t("link.guardedWhy")}>
                  <Typography
                    component="span"
                    variant="caption"
                    sx={{ color: "text.secondary", cursor: "help" }}
                  >
                    {t("link.guarded")}
                  </Typography>
                </Tooltip>
              )}
            </Box>
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
          <Prose text={prose.full} />
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
              <Prose text={text} />
            </Box>
          ) : null)}
        </Paper>
      )}

      {/*
        Ход обработки заменил перечень страт, который стоял здесь раньше.
        Перечень называл буквы A и C, ничего к ним не добавляя, и повторял
        фишки страт из шапки. Диаграмма выводится из той же конфигурации, но
        говорит, что именно технология делает и на каком шаге.
      */}
      {Object.keys(tech.configuration).length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>{t("configFlow.title")}</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1.5 }}>
            {t("configFlow.lead")}
          </Typography>
          <ConfigFlow
            configuration={tech.configuration}
            variable={tech.configuration_variable}
          />
        </Paper>
      )}

      {Object.keys(tech.configuration).length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>{t("techCard.configuration")}</Typography>
          {/*
            Без этой строки читатель не может отличить значение, сверенное с
            первоисточником, от значения по умолчанию, которое никто не смотрел.
            Выглядят они одинаково, а утверждают разное.
          */}
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
            {t("techCard.configurationLead")}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
            {tech.configuration_reviewed
              ? t("techCard.configurationReviewed", { date: tech.configuration_reviewed })
              : t("techCard.configurationUnreviewed")}
          </Typography>
          {/*
            Строки идут в порядке схемы и сгруппированы по стратам, а не в том
            порядке, в каком ключи легли в JSON. Порядок схемы совпадает с
            порядком обработки запроса, поэтому таблица читается сверху вниз
            как устройство системы, а не как алфавитный список свойств.
          */}
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t("techCard.dimension")}</TableCell>
                  <TableCell>{t("techCard.value")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {STRATA.map((stratum) => {
                  const rows = DIMENSIONS.filter(
                    (d) =>
                      d.stratum === stratum.code &&
                      (d.code in tech.configuration ||
                        tech.configuration_inapplicable.includes(d.code))
                  );
                  if (rows.length === 0) return null;
                  return [
                    <TableRow key={`h-${stratum.code}`}>
                      <TableCell
                        colSpan={2}
                        sx={{ borderBottom: 0, pt: 2, pb: 0.5 }}
                      >
                        <Typography
                          variant="caption"
                          sx={{
                            textTransform: "uppercase",
                            letterSpacing: "0.06em",
                            fontSize: "0.66rem",
                            color: "text.secondary",
                          }}
                        >
                          {t(`stratum.${stratum.code}`, { defaultValue: stratum.code })}
                        </Typography>
                      </TableCell>
                    </TableRow>,
                    ...rows.map((dim) => {
                      const inapplicable = tech.configuration_inapplicable.includes(dim.code);
                      const val = tech.configuration[dim.code];
                      const variable = tech.configuration_variable.includes(dim.code);
                      const note = tech.parse_notes.find((n) => n.code === dim.code);
                      const label = getDimensionLabel(dim.code, i18n.language);
                      const own = !inapplicable && val !== dim.default;
                      return (
                        <TableRow
                          key={dim.code}
                          sx={{ "& > td": { borderBottom: note ? 0 : undefined } }}
                        >
                          <TableCell sx={{ verticalAlign: "top", width: "42%", opacity: inapplicable ? 0.6 : 1 }}>
                            <Typography variant="body2" sx={{ fontWeight: own ? 600 : 400 }}>
                              {label?.name ?? dim.code}
                            </Typography>
                            {/*
                              Вопрос под именем и есть определение измерения.
                              Имя «Компоновка» без него так же непрозрачно, как
                              код D3: читателю нужно знать, о чём измерение
                              вообще, а не только как оно называется.
                            */}
                            {label && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ display: "block", lineHeight: 1.4 }}
                              >
                                {label.question}
                              </Typography>
                            )}
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              sx={{ fontFamily: "monospace", fontSize: "0.68rem" }}
                            >
                              {dim.code}
                            </Typography>
                          </TableCell>
                          {/*
                            Три разных утверждения о значении показываются
                            по-разному. Переменное значение выбирается системой
                            во время работы, и без пометки читатель принял бы
                            записанное за единственное. Неприменимое измерение
                            значения не имеет вовсе; строка остаётся, потому
                            что её отсутствие читалось бы как «забыли».
                          */}
                          <TableCell sx={{ verticalAlign: "top" }}>
                            {inapplicable ? (
                              <Typography variant="caption" color="text.secondary">
                                {t("techCard.dimensionInapplicable")}
                              </Typography>
                            ) : (
                              <>
                                <Typography
                                  variant="body2"
                                  sx={{ fontWeight: own ? 600 : 400, color: own ? "text.primary" : "text.secondary" }}
                                >
                                  {getValueLabel(dim.code, val, i18n.language) ?? val}
                                </Typography>
                                <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", alignItems: "baseline" }}>
                                  <Typography
                                    variant="caption"
                                    color="text.secondary"
                                    sx={{ fontFamily: "monospace", fontSize: "0.68rem" }}
                                  >
                                    {val}
                                  </Typography>
                                  {!own && (
                                    <Typography variant="caption" color="text.secondary">
                                      {t("techCard.dimensionDefaultMark")}
                                    </Typography>
                                  )}
                                  {variable && (
                                    <Typography variant="caption" color="text.secondary">
                                      {t("techCard.dimensionVariable")}
                                    </Typography>
                                  )}
                                </Box>
                                {/*
                                  Обоснование прямо под значением, а не в
                                  сноске. Конфигурация — единственное место
                                  портала, где решение принял человек: у уровня
                                  показан вывод правила, у свидетельства —
                                  источник, и только здесь значение появлялось
                                  без основания.
                                */}
                                {note && <ParseNoteBlock note={note} />}
                              </>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    }),
                  ];
                })}
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
