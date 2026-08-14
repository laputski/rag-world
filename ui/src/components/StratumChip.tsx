import { Box, Tooltip } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import { MONO, stratumColor, type ThemeMode } from "../theme";

/**
 * The stratum chip: the letter of the code and its colour.
 *
 * Colour here is the only saturated element of the interface, and it means the
 * stratum of a decision. The letter duplicates the colour so that the chip stays
 * readable under colour blindness and in black-and-white print.
 */

interface Props {
  stratum: string;
  /** Show the full name of the stratum beside the code. */
  withName?: boolean;
  count?: number;
}

export function StratumChip({ stratum, withName, count }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const color = stratumColor(stratum, theme.palette.mode as ThemeMode);
  const name = t(`stratum.${stratum}`, { defaultValue: stratum });

  return (
    <Tooltip title={withName ? "" : name} enterDelay={300}>
      <Box
        sx={{
          display: "inline-flex",
          alignItems: "center",
          gap: 0.6,
          fontSize: "0.78rem",
          color: "text.secondary",
        }}
      >
        <Box
          component="span"
          sx={{
            fontFamily: MONO,
            fontWeight: 700,
            fontSize: "0.72rem",
            color,
            border: `1px solid ${color}`,
            borderRadius: "3px",
            px: 0.5,
            lineHeight: 1.45,
          }}
        >
          {stratum}
        </Box>
        {withName && <span>{name.replace(/^[A-G]\.\s*/, "")}</span>}
        {count != null && (
          <Box component="span" className="tabular" sx={{ color: "text.secondary" }}>
            {count}
          </Box>
        )}
      </Box>
    </Tooltip>
  );
}
