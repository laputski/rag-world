import { useEffect, useState } from "react";
import {
  Box, Button, Collapse, Link as MuiLink, Paper, Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { getStats } from "../api/client";
import type { RegistryStats } from "../api/types";
import { toBibTeX, toGost, toPlain } from "../citation";
import { MONO } from "../theme";
import { useDocumentHead } from "../useDocumentHead";
import { ATTENTION_ANCHOR } from "../anchors";
import { useHashScroll } from "../useHashScroll";

/**
 * About: how the data is arranged and how it is updated.
 *
 * The page exists because the portal asks to be trusted with numbers, and trust
 * is not given by a declaration of rigour but by the chance to check: to see the
 * rule, the collection schedule and the list of sources, and to download the
 * data itself.
 */

const DATA_FILES = [
  { name: "index.json", key: "about.fileIndex" },
  { name: "registry.json", key: "about.fileRegistry" },
  { name: "map.json", key: "about.fileMap" },
  { name: "changes.json", key: "about.fileChanges" },
  { name: "stats.json", key: "about.fileStats" },
  { name: "residuals.json", key: "about.fileResiduals" },
  { name: "candidates.json", key: "about.fileCandidates" },
  { name: "digest.json", key: "about.fileDigest" },
  { name: "feed.xml", key: "about.fileFeed" },
  { name: "feed.ru.xml", key: "about.fileFeedRu" },
];

/** The permanent address of the portal, for the request examples. */
const SITE = "https://ragworld.org";

/** The store holding the source data and the whole history of its changes. */
const REPOSITORY = "https://github.com/laputski/rag-world";

/** The sources collection actually runs against today. */
const SOURCES = ["arXiv", "OpenAlex", "GitHub", "PyPI", "Papers with Code",
                 "Awesome-GraphRAG"];

interface Release { tag: string; doi?: string }

/** A ready citation with a copy button. */
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
  useDocumentHead({
    title: t("head.about.title"),
    description: t("head.about.description"),
  });
  // GOST is of no use to an English-speaking reader: it is a Russian standard.
  const style = i18n.language === "ru" ? toGost : toPlain;
  useHashScroll();
  const [stats, setStats] = useState<RegistryStats | null>(null);
  const [release, setRelease] = useState<Release | null>(null);
  const [example, setExample] = useState(false);
  const [access, setAccess] = useState(false);

  useEffect(() => { getStats().then(setStats).catch(() => setStats(null)); }, []);
  useEffect(() => {
    fetch("/data/releases/index.json")
      .then((r) => (r.ok ? r.json() : { releases: [] }))
      .then((d) => setRelease((d.releases as Release[])?.[0] ?? null))
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

      {/*
        The second axis of the map.

        The portal explained the level and left the vertical unexplained
        anywhere: what it measured lived in two hints over the map and in the
        code. A reader who wondered what a point standing high meant had nowhere
        to go, and the word for it named an interpretation rather than the
        measurement, which for this portal is the wrong way round.

        The section is the address the hint over the map points at, so its
        identifier is part of that link and does not change lightly.
      */}
      <Typography variant="h5" id={ATTENTION_ANCHOR} sx={{ mb: 1, scrollMarginTop: 80 }}>
        {t("about.howAttention")}
      </Typography>
      {["howAttentionText", "howAttentionNorm", "howAttentionSmall", "howAttentionNot"].map((key) => (
        <Typography key={key} variant="body1" sx={{ mb: 1.5, lineHeight: 1.75 }}>
          {t(`about.${key}`)}
        </Typography>
      ))}
      <Box sx={{ mb: 3 }} />

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

      {/*
        The portal claims that every number of its own is checkable. An
        obligation follows towards a reader who spots an error or knows something
        the portal does not: to tell them what is accepted and in what form.
        Without such a section, an invitation to check stays an invitation to say
        nothing.
      */}
      <Typography variant="h5" sx={{ mb: 1 }}>{t("about.contribute")}</Typography>
      <Typography variant="body1" sx={{ mb: 1.5, lineHeight: 1.75 }}>
        {t("about.contributeLevel")}
      </Typography>
      <Box component="ul" sx={{ pl: 3, m: 0, mb: 1.5 }}>
        {["contributeAccepted", "contributeRejected"].map((key) => (
          <Box component="li" key={key} sx={{ mb: 0.5 }}>
            <Typography variant="body1" sx={{ lineHeight: 1.75 }}>{t(`about.${key}`)}</Typography>
          </Box>
        ))}
      </Box>
      <Typography variant="body1" sx={{ mb: 1.5, lineHeight: 1.75 }}>
        {t("about.contributeNew")}
      </Typography>
      <Typography variant="body1" sx={{ mb: 1.5, lineHeight: 1.75 }}>
        {t("about.contributeManual")}
      </Typography>
      {/*
        The example is collapsed: it is longer than the rule itself and gets in
        the way of a reader for whom the rule was enough. For anyone about to
        write, opening it costs a click.
      */}
      <Box sx={{ mb: 1.5 }}>
        <MuiLink component="button" onClick={() => setExample((v) => !v)} variant="body2">
          {example ? t("about.exampleHide") : t("about.exampleShow")}
        </MuiLink>
        <Collapse in={example}>
          <Paper variant="outlined" sx={{ p: 2, mt: 1, maxWidth: "70ch" }}>
            <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.75 }}>
              {t("about.exampleGoodTitle")}
            </Typography>
            <Box component="pre" sx={{
              fontFamily: MONO, fontSize: "0.78rem", lineHeight: 1.65, m: 0, mb: 2,
              p: 1.5, bgcolor: "action.hover", borderRadius: 1,
              overflowX: "auto", whiteSpace: "pre-wrap",
            }}>
              {t("about.exampleGood")}
            </Box>
            <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.75 }}>
              {t("about.exampleBadTitle")}
            </Typography>
            <Box component="pre" sx={{
              fontFamily: MONO, fontSize: "0.78rem", lineHeight: 1.65, m: 0, mb: 1.5,
              p: 1.5, bgcolor: "action.hover", borderRadius: 1,
              overflowX: "auto", whiteSpace: "pre-wrap",
            }}>
              {t("about.exampleBad")}
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.75 }}>
              {t("about.exampleBadWhy")}
            </Typography>
          </Paper>
        </Collapse>
      </Box>

      {/*
        The section used to say a channel for reports was being chosen. It is
        chosen: the repository is open, and a report has a form. Both roads are
        named together with their price — a proposal needs a link and an edit
        needs a justification, or review returns it to its author anyway.
      */}
      <Typography variant="body1" sx={{ mb: 1.5, lineHeight: 1.75 }}>
        {t("about.contributeChannel")}
      </Typography>
      <Box component="ul" sx={{ pl: 3, m: 0, mb: 3 }}>
        <Box component="li" sx={{ mb: 0.5 }}>
          <Typography variant="body1" sx={{ lineHeight: 1.75 }}>
            <MuiLink href={`${REPOSITORY}/issues/new/choose`}>
              {t("about.contributeIssueLink")}
            </MuiLink>
            {" — "}{t("about.contributeIssue")}
          </Typography>
        </Box>
        <Box component="li">
          <Typography variant="body1" sx={{ lineHeight: 1.75 }}>
            <MuiLink href={`${REPOSITORY}/blob/main/CONTRIBUTING.md`}>
              {t("about.contributePullLink")}
            </MuiLink>
            {" — "}{t("about.contributePull")}
          </Typography>
        </Box>
      </Box>

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
        The section on connecting to the data.

        The portal shows the same information these files hold, only with markup.
        Whoever takes it by parsing pages gets worse data and breaks at the first
        edit to the layout, so the way to ask is stated outright, with examples
        that can be run without reading anything else.
      */}
      <Typography variant="h5" sx={{ mb: 1 }}>{t("about.machine")}</Typography>
      <Typography variant="body1" sx={{ mb: 1.5, lineHeight: 1.75 }}>
        {t("about.machineText")}
      </Typography>
      <Box component="ul" sx={{ pl: 3, m: 0, mb: 2 }}>
        {["machinePointIndex", "machinePointLlms", "machinePointGit",
          "machinePointRelease", "machinePointLicense"].map((key) => (
          <Box component="li" key={key} sx={{ mb: 0.75 }}>
            <Typography variant="body1" sx={{ lineHeight: 1.75 }}>{t(`about.${key}`)}</Typography>
          </Box>
        ))}
      </Box>

      <MuiLink
        component="button"
        onClick={() => setAccess((v) => !v)}
        sx={{ display: "block", mb: 1 }}
      >
        {access ? t("about.machineHide") : t("about.machineShow")}
      </MuiLink>
      <Collapse in={access}>
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2">{t("about.machineShell")}</Typography>
          <Snippet text={[
            `# ${t("about.machineShellComment")}`,
            `curl -s ${SITE}/data/index.json | jq '.datasets[] | {url, records}'`,
            "",
            `curl -s ${SITE}/data/registry.json \\`,
            "  | jq '.technologies[] | select(.level == \"L5\") | {id, name, level}'",
          ].join("\n")} />
        </Paper>
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2">{t("about.machinePython")}</Typography>
          <Snippet text={[
            "import urllib.request, json",
            "",
            `url = "${SITE}/data/registry.json"`,
            "with urllib.request.urlopen(url) as response:",
            "    registry = json.load(response)",
            "",
            "for tech in registry[\"technologies\"]:",
            "    if tech[\"configuration\"].get(\"A4\") == \"graph\":",
            "        print(tech[\"id\"], tech[\"level\"], tech[\"name\"])",
          ].join("\n")} />
        </Paper>
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2">{t("about.machineGit")}</Typography>
          <Snippet text={[
            `git clone ${REPOSITORY}`,
            "",
            `# ${t("about.machineGitComment")}`,
            "ls rag-world/data/technologies/",
            "cat rag-world/data/evidence/2026-08.jsonl",
          ].join("\n")} />
        </Paper>
      </Collapse>

      {/*
        A release is what to cite: the state of a record changes, and a citation
        of the current state will in time support something other than what it
        supported. The release tag therefore stands in every example.
      */}
      {release && (
        <>
          <Typography variant="h5" sx={{ mb: 1 }}>{t("about.cite")}</Typography>
          <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle2">{t("cite.gost")}</Typography>
            <Snippet text={style({ release: release.tag, doi: release.doi })} />
          </Paper>
          <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle2">{t("cite.bibtex")}</Typography>
            <Snippet text={toBibTeX({ release: release.tag, doi: release.doi })} />
          </Paper>
          <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
            <Typography variant="subtitle2">{t("cite.recordTitle")}</Typography>
            <Snippet text={style({
              release: release.tag,
              doi: release.doi,
              technology: { id: "pathrag", name: "PathRAG" },
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
