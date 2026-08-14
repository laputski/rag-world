import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Box, Typography, Paper, Chip, Alert, CircularProgress, Collapse, Divider, Link as MuiLink,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tooltip,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { getTechnology } from "../api/client";
import { getTechProse, getDimensionLabel, getValueLabel } from "../i18n/index";
import { LevelBadge } from "../components/LevelBadge";
import { ConfigGlyph } from "../components/ConfigGlyph";
import { ConfigFlow } from "../components/ConfigFlow";
import { StratumChip } from "../components/StratumChip";
import { DIMENSIONS, STRATA } from "../schema.generated";
import { BASE_CONFIGURATION_ID } from "../components/BaseConfiguration";
import { useDocumentHead } from "../useDocumentHead";
import type { ParseNote, RegistryTechnology } from "../api/types";

/**
 * The prose of a card: paragraphs rather than a wall.
 *
 * The texts are stored with a blank line between paragraphs, as in any ordinary
 * source. Without that split a description of four hundred words comes out as
 * one block, which a reader scrolls past without reading.
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
 * The justification of one decision of the configuration reading.
 *
 * It is shown collapsed: a reader who wants the value finds the justification in
 * the way, and a reader who does not believe the value needs it. Opening it is
 * one click, and it does not lead away from the page.
 *
 * "What the system does" and "why the value follows" are kept apart on purpose:
 * the first is checked against the source, the second against the schema.
 */
/**
 * The justification of the reading: why a dimension holds the value it does.
 *
 * The translation goes record by record and is stored beside the original, as in
 * the residual vocabulary: a justification means nothing apart from the
 * dimension it belongs to. While a record is untranslated, the Russian text is
 * shown with a note saying so — a blank space and a silent Russian paragraph
 * look equally like a breakage.
 */
function ParseNoteBlock({ note }: { note: ParseNote }) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);

  // The justifications are translated record by record, and until that is done
  // some cards stay Russian. The reader is told so outright on the cards where
  // it is the case: a blank space or a silent Russian paragraph is worse than a
  // note.
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
          The `data-basis` mark names the one place on a card where Russian text
          may legitimately stand in the English version. A test uses the same
          mark to tell a deliberate omission from a forgotten translation.
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
 * The card of one technology.
 *
 * The facts come from the registry and the texts from the localisation resources
 * by `prose_id`. The heading "task, barriers, solutions" applies to every record
 * that has such a text, not only to those that made it into the earlier article
 * about paradigms.
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
    // One record is requested rather than the whole registry: a card is the
    // page people most often arrive at from an outside link, and it has no
    // reason to pay for sixty-eight records that are not its own.
    getTechnology(id)
      .then((found) => {
        setTech(found);
        setError(null);
      })
      .catch(() => {
        setTech(null);
        setError(t("techCard.notFound"));
      })
      .finally(() => setLoading(false));
  }, [id, t]);

  // The tab title and description come from the record itself. The hook is
  // called before the loading and error returns, because the order of hook calls
  // has to be the same on every render.
  const prose = getTechProse(tech?.prose_id ?? null, i18n.language);
  useDocumentHead({
    title: tech?.name,
    description: prose.short ?? tech?.summary ?? undefined,
  });

  if (loading) return <CircularProgress sx={{ display: "block", mx: "auto", my: 8 }} />;
  if (error) return <Alert severity="info" sx={{ m: 2 }}>{error}</Alert>;
  if (!tech) return null;

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
        A source the portal could not open itself is marked right here. The
        portal rests on every claim of its own being checkable, and "the links
        are checked weekly" is a claim too. For three addresses it is untrue:
        publishers answer a robot with a refusal on rights, and only a person can
        confirm them. Saying nothing would mean passing the unchecked off as
        checked.
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
        The short summary comes from the localised prose rather than from the
        registry field: the field holds Russian text, and in the English version
        it would be a Russian paragraph in the middle of the page. The field
        stays as a fallback — a record may have no prose, and then a Russian line
        is better than nothing.
      */}
      {(prose.short || tech.summary) && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="body2">{prose.short ?? tech.summary}</Typography>
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
        The processing diagram replaced a list of strata that used to stand
        here. The list named the letters A and C and added nothing to them, and
        it repeated the stratum chips from the header. The diagram is derived
        from the same configuration but says what the technology actually does,
        and at which step.
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
            Without this line a reader cannot tell a value checked against the
            primary source from a base value nobody has looked at. They look
            alike and assert different things.
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
            The rows follow the order of the schema and are grouped by stratum,
            rather than the order the keys happened to land in the JSON. The
            schema order matches the order a query is processed in, so the table
            reads top to bottom as the make-up of a system rather than as an
            alphabetical list of properties.
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
                              The question under the name is the definition of
                              the dimension. The name "Context assembly" without
                              it is as opaque as the code D3: a reader needs to
                              know what the dimension is about at all, not only
                              what it is called.
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
                            Three different claims about a value are shown
                            differently. A variable value is chosen by the system
                            while it runs, and without a mark a reader would take
                            what is written for the only one. An inapplicable
                            dimension has no value at all; the row stays, because
                            its absence would read as an oversight.
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
                                    <MuiLink
                                      href={`/article#${BASE_CONFIGURATION_ID}`}
                                      variant="caption"
                                      color="text.secondary"
                                    >
                                      {t("techCard.dimensionDefaultMark")}
                                    </MuiLink>
                                  )}
                                  {variable && (
                                    <Typography variant="caption" color="text.secondary">
                                      {t("techCard.dimensionVariable")}
                                    </Typography>
                                  )}
                                </Box>
                                {/*
                                  The justification sits directly under the
                                  value rather than in a footnote. The
                                  configuration is the one place on the portal
                                  where a person made the decision: a level shows
                                  the output of the rule, a piece of evidence
                                  shows its source, and only here did a value
                                  used to appear with no grounds at all.
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

      {/* Why the level is what it is: the output of the rule and the evidence it
          stands on. Without this section a level is a claim the reader has no
          means to check. */}
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
              // Unsatisfied levels fall into two different cases. Those above
              // the current one are the road ahead. Those below mean a bypass:
              // the level was reached by another route, and that is worth
              // explaining, or a reader takes the gap for an error.
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
