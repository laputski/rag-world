import { Box, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import { DIMENSIONS, STRATA } from "../schema.generated";
import { getDimensionLabel, getValueLabel } from "../i18n/index";
import { stratumColor, type ThemeMode } from "../theme";

/**
 * Базовая конфигурация: точка отсчёта, от которой измеряется всё остальное.
 *
 * Раздел заведён потому, что портал ссылался на неё повсюду и нигде не
 * показывал. На карточке значение помечалось «как в базовой конфигурации», в
 * ходе обработки шаг помечался «без отличий от базовой», а посмотреть, какова
 * она и почему такова, было негде: умолчания жили в схеме и приезжали в
 * интерфейс, но ни одна страница их не выводила.
 *
 * Это противоречило тому, на чём портал стоит. У уровня показан вывод правила,
 * у значения измерения — обоснование разбора, у числа — происхождение, и только
 * точка отсчёта, относительно которой считаются все отступления, оставалась
 * невидимой и ничем не обоснованной.
 *
 * Таблица собирается из самой схемы, а не переписывается в текст статьи: второе
 * описание разошлось бы с первым при первой же правке умолчания. Обоснования
 * хранятся в локализации, потому что переводятся, а коды не переводятся.
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
        Оговорка о двух измерениях, где «ничего не делаем» невозможно, стоит
        отдельно и до таблицы: без неё читатель, дошедший до строки A5, решит,
        что правило нарушено, и будет прав по видимости.
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
