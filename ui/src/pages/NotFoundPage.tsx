import { Box, Button, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { useNavigate, useRouteError, isRouteErrorResponse } from "react-router-dom";

/**
 * Страница для адреса, которого нет.
 *
 * Портал статический, и правило переписывания отдаёт index.html на любой
 * адрес — иначе прямая ссылка на карточку не открывалась бы. Обратная сторона:
 * опечатка в адресе доходит до приложения, и без этой страницы читатель видел
 * отладочный экран маршрутизатора с обращением к разработчику.
 *
 * Служит и разделом «не найдено», и запасным на случай ошибки в любой другой
 * странице: сломанная страница не должна выглядеть как сломанный портал.
 */
export function NotFoundPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const error = useRouteError();

  const unexpected = error && !(isRouteErrorResponse(error) && error.status === 404);

  return (
    <Box sx={{ maxWidth: 620, mx: "auto", px: 3, py: 10, textAlign: "left" }}>
      <Typography variant="h4" sx={{ mb: 1.5 }}>
        {unexpected ? t("notFound.brokenTitle") : t("notFound.title")}
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        {unexpected ? t("notFound.brokenBody") : t("notFound.body")}
      </Typography>
      <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}>
        <Button variant="outlined" onClick={() => navigate("/")}>
          {t("notFound.toMap")}
        </Button>
        <Button variant="outlined" onClick={() => navigate("/registry")}>
          {t("notFound.toRegistry")}
        </Button>
      </Box>
    </Box>
  );
}
