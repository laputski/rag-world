import { Box, Tooltip, Typography } from "@mui/material";
import { MONO } from "../theme";

/**
 * The rate shown in the right column of the feed.
 *
 * The portal reports rates rather than absolute quantities: citations a month,
 * a level change over a period, the time since the evidence was last checked.
 * An absolute citation count is not comparable across fields and is out of date
 * the moment it is measured, whereas a rate is comparable and says something
 * about what is happening.
 *
 * Absent data is shown as a dash. A zero would say the quantity was measured and
 * came out zero, which is a different claim.
 */

interface Props {
  value: number | null | undefined;
  /** The label under the number: "cit./mo", "evidence" and the like. */
  unit: string;
  /** The provenance of the value, shown on hover. */
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

  // Every number carries its provenance: without one it must not be shown.
  return origin ? (
    <Tooltip title={origin} enterDelay={300}>{body}</Tooltip>
  ) : body;
}
