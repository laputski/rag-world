import { Box, Container, IconButton, Tooltip, Typography, MenuItem, Select, FormControl } from "@mui/material";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import SearchOutlinedIcon from "@mui/icons-material/SearchOutlined";
import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { ThemeMode } from "../theme";
import { MONO, SERIF_FAMILY } from "../theme";
import { Logo } from "../components/Logo";

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
  { to: "/digest", key: "nav.digest", end: false },
  { to: "/residuals", key: "nav.residuals", end: false },
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
        <Container
          maxWidth="xl"
          sx={{
            display: "flex", alignItems: "center", py: 1.25,
            gap: { xs: 1.5, md: 3 },
            // На узком экране шапка складывается в две строки: имя с
            // управлением сверху, навигация под ними во всю ширину. В одну
            // строку навигации оставалось около тридцати пикселей, то есть
            // полтора слова, и прокручивать её приходилось вслепую.
            flexWrap: { xs: "wrap", md: "nowrap" },
            rowGap: 1,
          }}
        >
          {/*
            Знак и словесный знак — одна ссылка, а не две рядом: две ссылки на
            один адрес удваивают остановку при обходе с клавиатуры и заставляют
            читалку экрана назвать цель дважды. Знак при этом скрыт от
            озвучивания, потому что слово рядом говорит то же самое.
          */}
          <Box
            component={NavLink}
            to="/"
            sx={{
              display: "flex", alignItems: "center", gap: 1,
              textDecoration: "none", flexShrink: 0,
            }}
          >
            {/*
              На узком экране знак уступает место: сорок шесть пикселей рядом с
              семью пунктами навигации стоят дороже узнавания, а словесный знак
              и без него говорит то же самое.
            */}
            <Box sx={{ display: { xs: "none", sm: "flex" } }}>
              <Logo size={26} title="" />
            </Box>
            <Typography
              component="span"
              sx={{
                fontFamily: SERIF_FAMILY, fontSize: "1.15rem", fontWeight: 600,
                color: "text.primary",
              }}
            >
              RAG World
            </Typography>
          </Box>

          {/*
            Навигация не переносится, а прокручивается вбок.

            С переносом семь пунктов на телефоне вставали в семь строк, шапка
            занимала весь экран, и до содержания приходилось долистывать. Полоса
            прокрутки прячется, но прокрутка остаётся: пункт, уехавший за край,
            достижим, тогда как спрятанный за кнопкой требует её найти.
          */}
          <Box
            component="nav"
            sx={{
              display: "flex", gap: 2.5, flexWrap: "nowrap",
              order: { xs: 3, md: 2 },
              width: { xs: "100%", md: "auto" },
              flexGrow: { xs: 0, md: 1 },
              overflowX: "auto", overflowY: "hidden",
              scrollbarWidth: "none",
              "&::-webkit-scrollbar": { display: "none" },
              // Маска у правого края говорит, что строка продолжается: обрез
              // по границе выглядит концом списка.
              maskImage: {
                xs: "linear-gradient(to right, #000 calc(100% - 24px), transparent)",
                md: "none",
              },
            }}
          >
            {NAV.map((item) => (
              <Typography
                key={item.to}
                component={NavLink}
                to={item.to}
                end={item.end}
                sx={{
                  fontSize: "0.88rem", textDecoration: "none", color: "text.secondary",
                  py: 0.25, borderBottom: "2px solid transparent", whiteSpace: "nowrap",
                  "&.active": { color: "text.primary", borderBottomColor: "text.primary" },
                  "&:hover": { color: "text.primary" },
                }}
              >
                {t(item.key)}
              </Typography>
            ))}
          </Box>

          {/*
            Поиск, язык и тема идут одной группой: на узком экране она остаётся
            в первой строке рядом с именем, а навигация уходит под них.

            Подсказка о сочетании клавиш на телефоне бесполезна: клавиатуры нет.
            Само поле поиска остаётся, потому что искать с телефона нужно.
          */}
          <Box
            sx={{
              display: "flex", alignItems: "center", gap: { xs: 1, md: 3 },
              order: { xs: 2, md: 3 }, ml: "auto", flexShrink: 0,
            }}
          >
          <Tooltip title={t("search.hint")}>
            <Box
              onClick={onOpenSearch}
              sx={{
                display: "flex", alignItems: "center", gap: 0.75, px: 1, py: 0.35,
                flexShrink: 0,
                border: 1, borderColor: "divider", borderRadius: 1, cursor: "pointer",
                color: "text.secondary",
                "&:hover": { color: "text.primary" },
              }}
            >
              <SearchOutlinedIcon sx={{ fontSize: 16 }} />
              <Typography
                sx={{ fontFamily: MONO, fontSize: "0.72rem", display: { xs: "none", md: "block" } }}
              >
                ⌘K
              </Typography>
            </Box>
          </Tooltip>

          <FormControl size="small" sx={{ flexShrink: 0 }}>
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
            <IconButton onClick={onToggleMode} size="small" sx={{ flexShrink: 0 }}>
              {mode === "light"
                ? <DarkModeOutlinedIcon fontSize="small" />
                : <LightModeOutlinedIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
          </Box>
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
