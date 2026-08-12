import { Box, Link as MuiLink, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { ConfigGlyph } from "./ConfigGlyph";
import { LevelBadge } from "./LevelBadge";
import { StratumChip } from "./StratumChip";
import { getTechProse } from "../i18n/index";
import { VelocityStat } from "./VelocityStat";

/**
 * Строка ленты технологий.
 *
 * Строка, а не карточка: карточки заставляют глаз обходить рамки, а материал
 * здесь сравнивают по колонкам. Разделяются строки волосяной линией.
 *
 * Слева отпечаток конфигурации, по центру содержание, справа величины. Такое
 * расположение позволяет листать ленту, читая только левый край и правую
 * колонку, и останавливаться на том, что заинтересовало.
 */

export interface FeedItem {
  id: string;
  /** Идентификатор локализованной прозы: из неё берётся краткая суть. */
  prose_id?: string | null;
  name: string;
  kind: string;
  groups: string[];
  configuration: Record<string, string>;
  core_idea?: string | null;
  level?: string | null;
  confidence?: number | null;
  evidence_basis?: string | null;
  attention?: number | null;
  /** Год подгруппы, по которой нормировано; null — нормировать было нечем. */
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
  const short = getTechProse(item.prose_id ?? null, i18n.language).short
    ?? item.core_idea;

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
          Краткая суть приходит из локализованной прозы. Поле реестра остаётся
          запасным вариантом и хранит русский текст: на английской версии он
          показывался прямо в перечне записей.
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
          Нормированное и измеренное значения показываются разными единицами.
          Подгруппа меньше пяти записей не нормируется, и её величина выражена в
          цитированиях за месяц, а не в долях медианы. Одна подпись на оба
          случая означала бы, что читатель сравнивает несравнимое, не зная об
          этом.
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
