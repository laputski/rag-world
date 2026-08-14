import { Box, Link as MuiLink, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { ConfigGlyph } from "./ConfigGlyph";
import { LevelBadge } from "./LevelBadge";
import { StratumChip } from "./StratumChip";
import { getTechProse } from "../i18n/index";
import { VelocityStat } from "./VelocityStat";

/**
 * A row of the technology feed.
 *
 * A row rather than a card: cards make the eye travel round a frame, and things
 * here are compared down columns. Rows are separated by a hairline.
 *
 * The configuration fingerprint is on the left, the content in the middle and
 * attention on the right. That arrangement lets a reader page through the feed
 * reading only the left edge or only one column, and stop at whatever catches
 * their interest.
 */

export interface FeedItem {
  id: string;
  /** The identifier of the localised prose the short summary comes from. */
  prose_id?: string | null;
  name: string;
  kind: string;
  groups: string[];
  configuration: Record<string, string>;
  summary?: string | null;
  level?: string | null;
  confidence?: number | null;
  evidence_basis?: string | null;
  attention?: number | null;
  /** The year of the subgroup it was normalised by; null when there was none. */
  attention_cohort?: string | null;
  evidence_count?: number | null;
  first_published?: string | null;
}

interface Props {
  item: FeedItem;
  onOpen?: (id: string) => void;
}

export function FeedRow({ item, onOpen }: Props) {
  const { t, i18n } = useTranslation();
  // The fallback comes from the artefact rather than from the Russian field:
  // prose exists for every record, and a Russian paragraph in the English
  // version would stand exactly where a translation had been forgotten.
  const short = getTechProse(item.prose_id ?? null, i18n.language).short
    ?? item.summary;

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "flex-start",
        gap: 2,
        py: 1.75,
        borderBottom: 1,
        borderColor: "divider",
      }}
    >
      <Box sx={{ pt: 0.5 }}>
        <ConfigGlyph configuration={item.configuration} size={26} />
      </Box>

      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <Box sx={{ display: "flex", alignItems: "baseline", gap: 1, flexWrap: "wrap" }}>
          <MuiLink
            href={`/tech/${item.id}`}
            onClick={onOpen ? (e) => { e.preventDefault(); onOpen(item.id); } : undefined}
            sx={{ fontSize: "1.02rem", fontWeight: 600, color: "text.primary" }}
          >
            {item.name}
          </MuiLink>
          <Typography variant="caption">
            {t(`kind.${item.kind}`, { defaultValue: item.kind })}
          </Typography>
          {item.first_published && (
            <Typography variant="caption" className="tabular">
              · {item.first_published}
            </Typography>
          )}
        </Box>

        {/*
          The short summary comes from the localised prose. The registry field
          stays as a fallback and holds Russian text: in the English version it
          used to show up right inside the list of records.
        */}
        {short && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              mt: 0.35,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {short}
          </Typography>
        )}

        <Box sx={{ display: "flex", gap: 1, mt: 0.75, flexWrap: "wrap" }}>
          {item.groups.map((g) => <StratumChip key={g} stratum={g} />)}
        </Box>
      </Box>

      <Box sx={{ display: "flex", alignItems: "center", gap: 2.5, flexShrink: 0 }}>
        <LevelBadge
          level={item.level ?? null}
          confidence={item.confidence}
          manual={item.evidence_basis === "manual"}
        />
        {/*
          The normalised and the measured value are shown in different units. A
          subgroup of fewer than five records is not normalised, and its quantity
          is in citations a month rather than in fractions of a median. One label
          for both cases would mean a reader comparing what is not comparable, so
          it is said outright.
        */}
        <VelocityStat
          value={item.attention}
          unit={
            item.attention_cohort
              ? t("map.attentionUnit")
              : t("map.attentionRaw")
          }
          origin={
            item.attention == null
              ? undefined
              : item.attention_cohort
                ? t("map.attentionOrigin")
                : t("map.attentionNotNormalized")
          }
        />
      </Box>
    </Box>
  );
}
