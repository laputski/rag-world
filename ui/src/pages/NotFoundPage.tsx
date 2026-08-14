import { Box, Button, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { useNavigate, useRouteError, isRouteErrorResponse } from "react-router-dom";
import { useDocumentHead } from "../useDocumentHead";

/**
 * The page for an address that does not exist.
 *
 * The portal is static, and the rewrite rule serves index.html for any address —
 * otherwise a direct link to a card would not open. So every typo in an address
 * reaches the application, and without this page the reader would meet the
 * router's debug screen addressing a developer.
 *
 * It serves both as the "not found" section and as a fallback for an error
 * inside any page: a broken page must not look like a broken portal.
 */
export function NotFoundPage() {

  const { t } = useTranslation();
  useDocumentHead({
    title: t("head.notFound.title"),
  });
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
