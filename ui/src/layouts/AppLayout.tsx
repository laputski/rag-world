import { Box, CircularProgress, Container, IconButton, Tooltip, Typography, MenuItem, Select, FormControl } from "@mui/material";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import SearchOutlinedIcon from "@mui/icons-material/SearchOutlined";
import { Suspense } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { ThemeMode } from "../theme";
import { MONO, SERIF_FAMILY } from "../theme";
import { Logo } from "../components/Logo";
import { GitHubIcon, LinkedInIcon } from "../components/BrandIcons";

/** The store of the source code and the data. */
const REPOSITORY = "https://github.com/laputski/rag-world";

/**
 * The frame of the portal: navigation on top and a wide field of content.
 *
 * A side menu gave way to a top bar because a portal is read rather than
 * administered: the horizontal goes to the content, and the sections fit in one
 * line. On the list pages the space on the left is taken by the facet panel,
 * which belongs to the content and not to the navigation.
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
            // On a narrow screen the header folds into two rows: the name and
            // the controls on top, the navigation below across the full width.
            // In one row the navigation had some thirty pixels left, that is, a
            // word and a half, and had to be scrolled blind.
            flexWrap: { xs: "wrap", md: "nowrap" },
            rowGap: 1,
          }}
        >
          {/*
            The mark and the wordmark are one link rather than two side by side:
            two links to one address double the stop in keyboard traversal and
            make a screen reader name the target twice. The mark is hidden from
            being announced, because the word beside it says the same thing.
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
              On a narrow screen the mark gives way: forty-six pixels beside
              seven navigation items cost more than the recognition is worth, and
              the wordmark says the same thing without it.
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
            The navigation does not wrap; it scrolls sideways.

            Wrapping put seven items on a phone into seven rows, the header took
            the whole screen, and the content had to be reached by scrolling. A
            scrollbar hides itself but the scrolling remains: an item that has
            gone off the edge is reachable, whereas one hidden behind a button
            has to be found first.
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
              // The mask at the right edge says the row continues: a cut at the
              // boundary looks like the end of the list.
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
            Search, language and theme travel as one group: on a narrow screen
            it stays in the first row beside the name, and the navigation moves
            below them.

            The hint about the keyboard shortcut is useless on a phone, there
            being no keyboard. The search field itself stays, because searching
            from a phone is a real need.
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

          <Tooltip title={t("nav.repository")}>
            <IconButton
              component="a"
              href={REPOSITORY}
              target="_blank"
              rel="noopener"
              size="small"
              aria-label={t("nav.repository")}
              sx={{ flexShrink: 0, color: "text.secondary" }}
            >
              <GitHubIcon size={17} />
            </IconButton>
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

      {/*
        The waiting state is shown in place of the content rather than in place
        of the whole portal: the header is already drawn and does not blink on a
        transition. The pages load on demand, so such waiting happens, but it is
        short.
      */}
      <Container maxWidth="xl" component="main" sx={{ flexGrow: 1, py: 3 }}>
        <Suspense
          fallback={<CircularProgress sx={{ display: "block", mx: "auto", my: 8 }} />}
        >
          <Outlet context={{ mode }} />
        </Suspense>
      </Container>

      <Box component="footer" sx={{ borderTop: 1, borderColor: "divider", py: 2 }}>
        <Container maxWidth="xl" sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
          <Typography variant="caption">Alexander Laputski, 2026</Typography>
          {/*
            A glyph instead of a word: a footer is scanned rather than read, and
            a recognisable glyph is found there faster than a line of text. The
            label stays for a screen reader, which would otherwise meet a link
            with no name.
          */}
          <Box
            component="a"
            href="https://www.linkedin.com/in/laputski/"
            target="_blank"
            rel="noopener"
            aria-label="LinkedIn"
            sx={{ display: "flex", alignItems: "center", color: "text.secondary",
                  "&:hover": { color: "primary.main" } }}
          >
            <LinkedInIcon size={15} />
          </Box>
          <Box
            component="a"
            href={REPOSITORY}
            target="_blank"
            rel="noopener"
            aria-label={t("nav.repository")}
            sx={{ display: "flex", alignItems: "center", color: "text.secondary",
                  "&:hover": { color: "primary.main" } }}
          >
            <GitHubIcon size={15} />
          </Box>
          <Typography variant="caption" sx={{ ml: "auto" }}>{t("footer.data")}</Typography>
        </Container>
      </Box>
    </Box>
  );
}
