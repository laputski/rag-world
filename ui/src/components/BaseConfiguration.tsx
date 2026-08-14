import { Box, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import { DIMENSIONS, STRATA } from "../schema.generated";
import { getDimensionLabel, getValueLabel } from "../i18n/index";
import { stratumColor, type ThemeMode } from "../theme";

/**
 * The base configuration: the reference point everything else is measured from.
 *
 * The section exists because the portal pointed at it everywhere and showed it
 * nowhere. On a card a value was marked "as in the base configuration", in the
 * processing flow a step was marked "no departures from the base", and there was
 * nowhere to look at what it was or why: the defaults lived in the schema and
 * reached the interface, and no page displayed them.
 *
 * That contradicted what the portal rests on. A level shows the output of the
 * rule, a dimension value shows the justification of the reading, a number shows
 * its provenance — and the reference point all departures are counted from
 * stayed invisible and unjustified.
 *
 * The table is assembled from the schema itself rather than written out in text:
 * a second description would diverge from the first at the first edit to a
 * default. The names live in the localisation because they are translated and
 * the codes are not.
 */

export const BASE_CONFIGURATION_ID = "base-configuration";

export function BaseConfiguration() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const mode = theme.palette.mode as ThemeMode;

  return (
    <Paper variant="outlined" sx={{ p: 3, mb: 3, scrollMarginTop: 80 }} id={BASE_CONFIGURATION_ID}>
      <Typography variant="h5" gutterBottom>{t("baseConfig.title")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2, fontStyle: "italic" }}>
        {t("baseConfig.intro")}
      </Typography>
      <Typography variant="body2" sx={{ mb: 1, lineHeight: 1.8, maxWidth: "68ch" }}>
        {t("baseConfig.principle")}
      </Typography>
      {/*
        The caveat about the dimensions where "do nothing" is impossible stands
        apart and before the table: without it a reader who reaches the row for
        A1 decides the rule is broken, and on the face of it they are right.
      */}
      <Typography variant="body2" sx={{ mb: 2.5, lineHeight: 1.8, maxWidth: "68ch" }}>
        {t("baseConfig.exceptions")}
      </Typography>

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: "32%" }}>{t("techCard.dimension")}</TableCell>
              <TableCell sx={{ width: "26%" }}>{t("baseConfig.value")}</TableCell>
              <TableCell>{t("baseConfig.reason")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {STRATA.map((stratum) => {
              const rows = DIMENSIONS.filter((d) => d.stratum === stratum.code);
              if (rows.length === 0) return null;
              return [
                <TableRow key={`h-${stratum.code}`}>
                  <TableCell colSpan={3} sx={{ borderBottom: 0, pt: 2, pb: 0.5 }}>
                    <Typography
                      variant="caption"
                      sx={{
                        textTransform: "uppercase", letterSpacing: "0.06em",
                        fontSize: "0.66rem", color: stratumColor(stratum.code, mode),
                      }}
                    >
                      {t(`stratum.${stratum.code}`, { defaultValue: stratum.code })}
                    </Typography>
                  </TableCell>
                </TableRow>,
                ...rows.map((dim) => {
                  const label = getDimensionLabel(dim.code, i18n.language);
                  return (
                    <TableRow key={dim.code}>
                      <TableCell sx={{ verticalAlign: "top" }}>
                        <Typography variant="body2">{label?.name ?? dim.code}</Typography>
                        <Typography
                          variant="caption" color="text.secondary"
                          sx={{ fontFamily: "monospace", fontSize: "0.68rem" }}
                        >
                          {dim.code}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ verticalAlign: "top" }}>
                        <Typography variant="body2">
                          {getValueLabel(dim.code, dim.default, i18n.language) ?? dim.default}
                        </Typography>
                        <Typography
                          variant="caption" color="text.secondary"
                          sx={{ fontFamily: "monospace", fontSize: "0.68rem" }}
                        >
                          {dim.default}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ verticalAlign: "top" }}>
                        <Typography variant="body2" sx={{ lineHeight: 1.55 }}>
                          {t(`baseConfig.why.${dim.code}`, { defaultValue: "" })}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  );
                }),
              ];
            })}
          </TableBody>
        </Table>
      </TableContainer>

      <Box sx={{ mt: 2.5 }}>
        <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.75, maxWidth: "68ch" }}>
          {t("baseConfig.note")}
        </Typography>
      </Box>
    </Paper>
  );
}
