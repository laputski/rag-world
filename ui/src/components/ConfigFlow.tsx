import { useMemo } from "react";
import { Box, Chip, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import { DIMENSIONS, STRATA } from "../schema.generated";
import { getValueLabel } from "../i18n/index";
import { stratumColor, type ThemeMode } from "../theme";

/**
 * Ход обработки: что технология делает и на каком шаге.
 *
 * Диаграмма выводится целиком из конфигурации записи и потому не может
 * разойтись с данными. Нарисованная руками схема архитектуры была бы
 * утверждением без источника, а через полгода ещё и утверждением неверным:
 * конфигурация меняется при пересмотре разбора, картинка не меняется никогда.
 *
 * Показаны только те измерения, где технология отступает от значения по
 * умолчанию. Это и есть её решения: страта без отступлений означает, что на
 * этом шаге система делает то же, что делает базовый поиск по векторам, и
 * перечислять там нечего. Полный набор значений, включая совпавшие с
 * умолчанием, остаётся ниже в таблице.
 *
 * Порядок страт A–G совпадает с порядком обработки запроса: представление
 * знаний, формулировка запроса, извлечение, формирование контекста, синтез,
 * эволюция состояния, оболочка ограничений. Поэтому диаграмма читается сверху
 * вниз как путь запроса, а не как произвольный список свойств.
 */

interface Props {
  configuration: Record<string, string>;
  /** Измерения, значение которых система выбирает во время работы. */
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
              Рельс слева несёт две вещи сразу: цвет страты, тот же, что в глифе
              и в фишках страт, и непрерывность линии между шагами. Непрерывная
              линия и делает список ходом обработки, а не перечнем.
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
                <Typography variant="body2" color="text.secondary">
                  {t("configFlow.defaultStep")}
                </Typography>
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
