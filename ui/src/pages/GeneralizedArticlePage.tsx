import { useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Box, Typography, Paper, Divider, Link as MuiLink, Modal, IconButton,
  List, ListItemButton, ListItemText,
} from "@mui/material";
import FullscreenOutlinedIcon from "@mui/icons-material/FullscreenOutlined";
import CloseOutlinedIcon from "@mui/icons-material/CloseOutlined";
import mermaid from "mermaid";
import { getGeneralizedContent } from "../generalizedData";
import { RichText } from "../components/RichText";

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function MermaidDiagram({ chart, theme }: { chart: string; theme: "light" | "dark" }) {
  const [svg, setSvg] = useState<string>("");
  const [fullscreenSvg, setFullscreenSvg] = useState<string>("");
  const [open, setOpen] = useState(false);
  const idRef = useRef(`m${Math.random().toString(36).slice(2, 9)}`);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: theme === "dark" ? "dark" : "neutral",
      securityLevel: "loose",
      themeVariables: theme === "dark" ? {
        primaryColor: "#1e293b", primaryTextColor: "#e2e8f0", primaryBorderColor: "#3b82f6",
        lineColor: "#64748b", secondaryColor: "#334155", tertiaryColor: "#0f172a", fontSize: "14px",
      } : {},
    });
    mermaid.render(idRef.current, chart).then((res) => setSvg(res.svg)).catch(() => setSvg(""));
  }, [chart, theme]);

  const handleOpen = () => {
    // Перерендерить в крупном масштабе для модального окна.
    const bigId = `big${idRef.current}`;
    mermaid.initialize({
      startOnLoad: false,
      theme: theme === "dark" ? "dark" : "neutral",
      securityLevel: "loose",
      themeVariables: theme === "dark" ? {
        primaryColor: "#1e293b", primaryTextColor: "#e2e8f0", primaryBorderColor: "#3b82f6",
        lineColor: "#64748b", secondaryColor: "#334155", tertiaryColor: "#0f172a", fontSize: "16px",
      } : { fontSize: "16px" },
      flowchart: { useMaxWidth: false },
    });
    mermaid.render(bigId, chart).then((res) => setFullscreenSvg(res.svg)).catch(() => setFullscreenSvg(""));
    setOpen(true);
  };

  return (
    <>
      <Box sx={{ position: "relative", mt: 2, mb: 1 }}>
        <Box
          dangerouslySetInnerHTML={{ __html: svg }}
          sx={{
            overflowX: "auto",
            cursor: "zoom-in",
            "& svg": { maxWidth: "100%", minHeight: "60px" },
          }}
          onClick={handleOpen}
        />
        <IconButton
          size="small"
          onClick={handleOpen}
          sx={{ position: "absolute", top: 0, right: 0, opacity: 0.5 }}
        >
          <FullscreenOutlinedIcon fontSize="small" />
        </IconButton>
      </Box>
      <Modal open={open} onClose={() => setOpen(false)} sx={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Box sx={{
          bgcolor: "background.paper", borderRadius: 2, p: 3, maxWidth: "95vw", maxHeight: "95vh",
          overflow: "auto", position: "relative",
        }}>
          <IconButton onClick={() => setOpen(false)} sx={{ position: "absolute", top: 8, right: 8 }}>
            <CloseOutlinedIcon />
          </IconButton>
          <Box dangerouslySetInnerHTML={{ __html: fullscreenSvg }} sx={{ "& svg": { maxWidth: "90vw" } }} />
        </Box>
      </Modal>
    </>
  );
}

/**
 * То, что кладёт в контекст оболочка. Имя поля обязано совпадать с её `mode`:
 * поле называлось здесь `theme`, оболочка передавала `mode`, и получалось
 * `undefined`. Схемы на этой странице рисовались светлыми и в тёмной теме, а
 * типы молчали: `useOutletContext<T>()` — приведение, а не проверка.
 */
interface OutletCtx { mode: "light" | "dark" }

export function GeneralizedArticlePage() {
  const { t, i18n } = useTranslation();
  const { mode } = useOutletContext<OutletCtx>();
  const content = getGeneralizedContent(i18n.language === "ru" ? "ru" : "en");

  return (
    <Box sx={{ display: "flex" }}>
      {/* Оглавление слева */}
      <Box sx={{ width: 200, flexShrink: 0, position: "sticky", top: 64, alignSelf: "flex-start", display: { xs: "none", md: "block" } }}>
        <List dense sx={{ pr: 1 }}>
          <ListItemButton onClick={() => scrollToId("abstract")} sx={{ py: 0.25 }}>
            <ListItemText primary={t("common.abstract")} slotProps={{ primary: { sx: { fontSize: "0.8rem" } } }} />
          </ListItemButton>
          {content.sections.map((s) => (
            <ListItemButton key={s.id} onClick={() => scrollToId(s.id)} sx={{ py: 0.25 }}>
              <ListItemText primary={s.title} slotProps={{ primary: { sx: { fontSize: "0.8rem" } } }} />
            </ListItemButton>
          ))}
          <ListItemButton onClick={() => scrollToId("refs")} sx={{ py: 0.25 }}>
            <ListItemText primary={t("common.sources")} slotProps={{ primary: { sx: { fontSize: "0.8rem" } } }} />
          </ListItemButton>
        </List>
      </Box>

      {/* Тело статьи */}
      <Box sx={{ flexGrow: 1, minWidth: 0, maxWidth: 800 }}>
        <Box id="abstract" sx={{ scrollMarginTop: 80, mb: 2 }}>
          <Typography variant="h4" sx={{ mb: 1 }}>{content.title}</Typography>
          {/*
            Раздел назван «Основания», а не «Статья», и разница существенна.
            «Статья» обещает читателю новость об области; он же получает модель,
            на которой держатся реестр и карта. Без этой строки непонятно, зачем
            в портале о технологиях лежит научный текст.
          */}
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1, maxWidth: "64ch" }}>
            {t("article.foundationsNote")}
          </Typography>
        </Box>

        <Paper variant="outlined" sx={{ p: 3, mb: 3, scrollMarginTop: 80 }}>
          <RichText sx={{ lineHeight: 1.8 }}>{content.abstractText}</RichText>
        </Paper>

        {content.sections.map((s) => (
          <Paper key={s.id} variant="outlined" sx={{ p: 3, mb: 3, scrollMarginTop: 80 }} id={s.id}>
            <Typography variant="h5" gutterBottom>{s.title}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2, fontStyle: "italic" }}>
              {s.intro}
            </Typography>
            <RichText sx={{ lineHeight: 1.8 }}>{s.content}</RichText>
            {s.diagram && <MermaidDiagram chart={s.diagram} theme={mode} />}
          </Paper>
        ))}

        {/* Источники */}
        <Paper variant="outlined" sx={{ p: 3, mb: 3, scrollMarginTop: 80 }} id="refs">
          <Typography variant="h5" gutterBottom>{t("common.sources")}</Typography>
          <Divider sx={{ mb: 2 }} />
          {content.refs.map((r, i) => (
            <Box key={i} id={`ref-${i + 1}`} sx={{ py: 0.3, scrollMarginTop: 80 }}>
              {r.url ? (
                <MuiLink href={r.url} target="_blank" rel="noopener" sx={{ color: "text.primary", fontSize: "0.82rem" }}>
                  {r.label}
                </MuiLink>
              ) : (
                <Typography component="span" variant="body2" sx={{ fontSize: "0.82rem" }}>{r.label}</Typography>
              )}
            </Box>
          ))}
        </Paper>
      </Box>
    </Box>
  );
}
