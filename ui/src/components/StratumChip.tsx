import { Box, Tooltip } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import { MONO, stratumColor, type ThemeMode } from "../theme";

/**
 * Метка страты: буква кода и её цвет.
 *
 * Цвет здесь — единственный насыщенный элемент интерфейса, и он всегда означает
 * страту решений. Буква дублирует цвет, чтобы метка оставалась читаемой при
 * дальтонизме и в чёрно-белой печати.
 */

interface Props {
  stratum: string;
  /** Показать полное название страты рядом с кодом. */
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
