import { Box, Tooltip, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import { MONO } from "../theme";

/**
 * The maturity level: a badge and a positional scale.
 *
 * A level is ordinal and is therefore encoded by position rather than colour: of
 * two hues a reader cannot say which is higher, and of seven positions they can
 * say at once.
 *
 * An absent level is shown as a state of its own and never as level zero: "not
 * studied" and "a hypothesis" are different claims, and passing the first off as
 * the second accuses a technology of something nobody knows about it.
 */

const LEVELS = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"];

interface Props {
  level: string | null;
  confidence?: number | null;
  /** The level was entered by a person, where no machine-readable source
   *  exists. */
  manual?: boolean;
  showScale?: boolean;
}

export function LevelBadge({ level, confidence, manual, showScale = true }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();

  const index = level ? LEVELS.indexOf(level) : -1;
  const known = index >= 0;

  const hint = known
    ? [
        t(`level.${level}`),
        confidence != null ? `${t("map.confidence")}: ${confidence.toFixed(2)}` : "",
        manual ? t("techCard.manualBasis") : "",
      ].filter(Boolean).join(" · ")
    : t("level.unknown");

  return (
    <Tooltip title={hint} enterDelay={300}>
      <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.75 }}>
        <Typography
          component="span"
          sx={{
            fontFamily: MONO,
            fontSize: "0.8rem",
            fontWeight: 600,
            color: known ? "text.primary" : "text.secondary",
            fontStyle: known ? "normal" : "italic",
          }}
        >
          {known ? level : "—"}
        </Typography>
        {showScale && (
          <Box sx={{ display: "inline-flex", gap: "2px", alignItems: "center" }}>
            {LEVELS.map((_, i) => (
              <Box
                key={i}
                sx={{
                  width: 4,
                  height: i <= index ? 11 : 5,
                  borderRadius: "1px",
                  bgcolor: i <= index ? "text.primary" : theme.palette.divider,
                  opacity: i <= index && confidence != null ? 0.35 + confidence * 0.65 : 1,
                }}
              />
            ))}
          </Box>
        )}
        {manual && (
          <Typography component="span" variant="caption" sx={{ fontStyle: "italic" }}>
            {t("techCard.manualShort")}
          </Typography>
        )}
      </Box>
    </Tooltip>
  );
}
