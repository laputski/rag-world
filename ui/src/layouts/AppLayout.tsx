import { Box, Container, IconButton, Tooltip, Typography, MenuItem, Select, FormControl } from "@mui/material";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import SearchOutlinedIcon from "@mui/icons-material/SearchOutlined";
import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { ThemeMode } from "../theme";
import { MONO, SERIF_FAMILY } from "../theme";

/**
 * Каркас портала: верхняя навигация и широкое поле содержания.
 *
 * Боковое меню уступило место верхней панели, потому что портал читают, а не
 * администрируют: горизонталь отдана содержанию, а разделов немного и они
 * помещаются в строку. На списочных страницах место слева занимает колонка
 * фасетов, которая относится к содержанию, а не к навигации.
 */

const NAV = [
  { to: "/", key: "nav.map", end: true },
  { to: "/registry", key: "nav.registry", end: false },
  { to: "/changes", key: "nav.changes", end: false },
  { to: "/article", key: "nav.generalized", end: false },
  { to: "/about", key: "nav.about", end: false },
];

interface Props {
  mode: ThemeMode;
  onToggleMode: () => void;
  lang: "ru" | "en";
  onSetLang: (lang: "ru" | "en") => void;
  onOpenSearch: () => void;
}

export function AppLayout({ mode, onToggleMode, lang, onSetLang, onOpenSearch }: Props) {
  const { t } = useTranslation();

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Box
        component="header"
        sx={{
          position: "sticky", top: 0, zIndex: 10,
          bgcolor: "background.default",
          borderBottom: 1, borderColor: "divider",
        }}
      >
        <Container maxWidth="xl" sx={{ display: "flex", alignItems: "center", gap: 3, py: 1.25 }}>
          <Typography
            component={NavLink}
            to="/"
            sx={{
              fontFamily: SERIF_FAMILY, fontSize: "1.15rem", fontWeight: 600,
              color: "text.primary", textDecoration: "none", flexShrink: 0,
            }}
          >
            RAG World
          </Typography>

          <Box component="nav" sx={{ display: "flex", gap: 2.5, flexGrow: 1, flexWrap: "wrap" }}>
            {NAV.map((item) => (
              <Typography
                key={item.to}
                component={NavLink}
                to={item.to}
                end={item.end}
                sx={{
                  fontSize: "0.88rem", textDecoration: "none", color: "text.secondary",
                  py: 0.25, borderBottom: "2px solid transparent",
                  "&.active": { color: "text.primary", borderBottomColor: "text.primary" },
                  "&:hover": { color: "text.primary" },
                }}
              >
                {t(item.key)}
              </Typography>
            ))}
          </Box>

          <Tooltip title={t("search.hint")}>
            <Box
              onClick={onOpenSearch}
              sx={{
                display: "flex", alignItems: "center", gap: 0.75, px: 1, py: 0.35,
                border: 1, borderColor: "divider", borderRadius: 1, cursor: "pointer",
                color: "text.secondary",
                "&:hover": { color: "text.primary" },
              }}
            >
              <SearchOutlinedIcon sx={{ fontSize: 16 }} />
              <Typography sx={{ fontFamily: MONO, fontSize: "0.72rem" }}>⌘K</Typography>
            </Box>
          </Tooltip>

          <FormControl size="small">
            <Select
              value={lang}
              onChange={(e) => onSetLang(e.target.value as "ru" | "en")}
              sx={{ "& .MuiSelect-select": { py: 0.35, fontSize: "0.75rem" } }}
            >
              <MenuItem value="ru">RU</MenuItem>
              <MenuItem value="en">EN</MenuItem>
            </Select>
          </FormControl>

          <Tooltip title={mode === "light" ? t("theme.dark") : t("theme.light")}>
            <IconButton onClick={onToggleMode} size="small">
              {mode === "light"
                ? <DarkModeOutlinedIcon fontSize="small" />
                : <LightModeOutlinedIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
        </Container>
      </Box>

      <Container maxWidth="xl" component="main" sx={{ flexGrow: 1, py: 3 }}>
        <Outlet context={{ mode }} />
      </Container>

      <Box component="footer" sx={{ borderTop: 1, borderColor: "divider", py: 2 }}>
        <Container maxWidth="xl" sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
          <Typography variant="caption">Alexander Laputski, 2026</Typography>
          <Typography
            variant="caption" component="a" href="https://www.linkedin.com/in/laputski/"
            target="_blank" rel="noopener"
            sx={{ color: "primary.main", textDecoration: "none" }}
          >
            LinkedIn
          </Typography>
          <Typography variant="caption" sx={{ ml: "auto" }}>{t("footer.data")}</Typography>
        </Container>
      </Box>
    </Box>
  );
}
