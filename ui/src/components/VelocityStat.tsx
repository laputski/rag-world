import { Box, Tooltip, Typography } from "@mui/material";
import { MONO } from "../theme";

/**
 * Показатель скорости в правой колонке ленты.
 *
 * Портал сообщает не абсолютные величины, а скорости: цитирования в месяц,
 * изменение уровня за период, срок с последней проверки свидетельств.
 * Абсолютное число цитирований несравнимо между областями и устаревает в
 * момент измерения, а скорость сравнима и говорит о происходящем сейчас.
 *
 * Отсутствие данных показывается прочерком. Ноль означал бы, что величину
 * измерили и она равна нулю, а это другое утверждение.
 */

interface Props {
  value: number | null | undefined;
  /** Подпись под числом: «цит./мес», «свидетельств» и подобное. */
  unit: string;
  /** Происхождение значения: показывается при наведении. */
  origin?: string;
  fractionDigits?: number;
}

export function VelocityStat({ value, unit, origin, fractionDigits = 1 }: Props) {
  const known = value != null && Number.isFinite(value);
  const body = (
    <Box sx={{ textAlign: "right", minWidth: 64 }}>
      <Typography
        className="tabular"
        sx={{
          fontFamily: MONO,
          fontSize: "0.95rem",
          fontWeight: 600,
          lineHeight: 1.2,
          color: known ? "text.primary" : "text.secondary",
        }}
      >
        {known ? value!.toFixed(fractionDigits) : "—"}
      </Typography>
      <Typography
        variant="caption"
        sx={{
          display: "block",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          fontSize: "0.64rem",
        }}
      >
        {unit}
      </Typography>
    </Box>
  );

  // Каждое число несёт происхождение: без него его нельзя показывать (K2).
  return origin ? (
    <Tooltip title={origin} enterDelay={300}>{body}</Tooltip>
  ) : body;
}
