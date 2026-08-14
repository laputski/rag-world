import { useMemo } from "react";
import { Box, Chip, Link as MuiLink, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import { DIMENSIONS, STRATA } from "../schema.generated";
import { getValueLabel } from "../i18n/index";
import { stratumColor, type ThemeMode } from "../theme";
import { BASE_CONFIGURATION_ID } from "./BaseConfiguration";

/**
 * The processing flow: what a technology does, and at which step.
 *
 * The diagram is derived entirely from the configuration of the record and
 * therefore cannot diverge from the data. A diagram drawn by hand would be a
 * claim without a source, and in half a year a wrong one as well: the
 * configuration changes when the reading is revised, and a picture does not.
 *
 * Only the dimensions where the technology departs from the base value are
 * shown. Those are its decisions: a stratum without departures means that at
 * this step the system does what plain vector search does, and there is nothing
 * to list. The full set of values, the matching ones included, stays in the
 * table below.
 *
 * The order of the strata A–G matches the order a query is processed in:
 * knowledge representation, query formulation, retrieval, context assembly,
 * synthesis and control, state evolution, constraint envelope. The diagram
 * therefore reads top to bottom as the path of a query rather than as an
 * arbitrary list of properties.
 */

interface Props {
  configuration: Record<string, string>;
  /** Dimensions whose value the system chooses at run time. */
  variable?: string[];
}

interface Step {
  stratum: string;
  decisions: { code: string; value: string; label: string; variable: boolean }[];
}

export function ConfigFlow({ configuration, variable = [] }: Props) {
  const theme = useTheme();
  const { t, i18n } = useTranslation();
  const mode = theme.palette.mode as ThemeMode;
  const lang = i18n.language;

  const steps: Step[] = useMemo(
    () =>
      STRATA.map((stratum) => ({
        stratum: stratum.code,
        decisions: DIMENSIONS.filter((d) => d.stratum === stratum.code)
          .filter((d) => {
            const value = configuration[d.code];
            return Boolean(value) && value !== d.default;
          })
          .map((d) => ({
            code: d.code,
            value: configuration[d.code],
            label: getValueLabel(d.code, configuration[d.code], lang) ?? configuration[d.code],
            variable: variable.includes(d.code),
          })),
      })),
    [configuration, variable, lang]
  );

  const total = steps.reduce((sum, s) => sum + s.decisions.length, 0);
  if (total === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        {t("configFlow.allDefault")}
      </Typography>
    );
  }

  return (
    <Box role="list" aria-label={t("configFlow.title")}>
      {steps.map((step, index) => {
        const color = stratumColor(step.stratum, mode);
        const idle = step.decisions.length === 0;
        return (
          <Box
            key={step.stratum}
            role="listitem"
            sx={{ display: "flex", gap: 1.5, alignItems: "stretch", opacity: idle ? 0.45 : 1 }}
          >
            {/*
              The rail on the left carries two things at once: the colour of
              the stratum, the same one the stratum chips use, and the continuity
              of a line between the steps. It is the unbroken line that makes the
              list a flow of processing rather than an enumeration.
            */}
            <Box
              sx={{ display: "flex", flexDirection: "column", alignItems: "center", width: 12 }}
              aria-hidden
            >
              <Box
                sx={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  bgcolor: idle ? "transparent" : color,
                  border: 2,
                  borderColor: color,
                  mt: 0.75,
                  flexShrink: 0,
                }}
              />
              {index < steps.length - 1 && (
                <Box sx={{ width: 2, flexGrow: 1, bgcolor: color, opacity: 0.35, minHeight: 12 }} />
              )}
            </Box>

            <Box sx={{ pb: 2, minWidth: 0, flexGrow: 1 }}>
              <Typography variant="caption" sx={{ display: "block", color: "text.secondary" }}>
                {t(`stratum.${step.stratum}`, { defaultValue: step.stratum })}
              </Typography>
              {idle ? (
                <MuiLink
                  href={`/article#${BASE_CONFIGURATION_ID}`}
                  variant="body2"
                  color="text.secondary"
                >
                  {t("configFlow.defaultStep")}
                </MuiLink>
              ) : (
                <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap", mt: 0.5 }}>
                  {step.decisions.map((d) => (
                    <Chip
                      key={d.code}
                      size="small"
                      variant="outlined"
                      sx={{ borderColor: color, height: "auto", py: 0.35 }}
                      label={
                        <Box sx={{ display: "flex", alignItems: "baseline", gap: 0.75 }}>
                          <Box
                            component="span"
                            sx={{ fontFamily: "monospace", fontSize: "0.68rem", opacity: 0.65 }}
                          >
                            {d.code}
                          </Box>
                          <Box component="span" sx={{ whiteSpace: "normal" }}>
                            {d.label}
                          </Box>
                          {d.variable && (
                            <Box
                              component="span"
                              sx={{ fontSize: "0.68rem", opacity: 0.65, whiteSpace: "nowrap" }}
                            >
                              {t("techCard.dimensionVariable")}
                            </Box>
                          )}
                        </Box>
                      }
                    />
                  ))}
                </Box>
              )}
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}
