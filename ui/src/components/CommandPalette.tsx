import { useEffect, useMemo, useRef, useState } from "react";
import { Box, Dialog, InputBase, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { getRegistry } from "../api/client";
import { MONO } from "../theme";
import { ConfigGlyph } from "./ConfigGlyph";
import { LevelBadge } from "./LevelBadge";
import type { FeedItem } from "./FeedRow";

/**
 * The quick search over the registry, opened by a keyboard shortcut.
 *
 * The registry fits in memory whole, so the search runs in the browser: it is
 * instant and there is no server to ask. Matches are looked for by name and by
 * alias, because technologies are often remembered by an abbreviation rather
 * than by a full name.
 *
 * The registry is read when the search is first opened rather than on page load.
 * The shell used to pull it, so eight hundred kilobytes came with every page for
 * a search the reader might never use. What has been read stays in memory, so
 * the second opening is instant.
 */

interface Props {
  onOpen: (id: string) => void;
  /** Lets the search be opened from outside: from the header button, not only
   *  by the shortcut. */
  registerOpener?: (open: () => void) => void;
}

const MAX_RESULTS = 8;

export function CommandPalette({ onOpen, registerOpener }: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const [items, setItems] = useState<(FeedItem & { aliases?: string[] })[]>([]);
  const [loading, setLoading] = useState(false);
  const requested = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Loading starts on the first opening and happens once. A failure leaves the
  // search empty and the portal working.
  useEffect(() => {
    if (!open || requested.current) return;
    requested.current = true;
    setLoading(true);
    getRegistry()
      .then((r) => setItems(r.technologies as unknown as FeedItem[]))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [open]);

  useEffect(() => {
    registerOpener?.(() => setOpen(true));
  }, [registerOpener]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return items.slice(0, MAX_RESULTS);
    const scored = items
      .map((item) => {
        const names = [item.name, ...(item.aliases ?? [])].map((n) => n.toLowerCase());
        const best = Math.min(
          ...names.map((n) => {
            const at = n.indexOf(needle);
            return at < 0 ? Number.POSITIVE_INFINITY : at;
          })
        );
        return { item, score: best };
      })
      .filter((r) => Number.isFinite(r.score))
      .sort((a, b) => a.score - b.score || a.item.name.localeCompare(b.item.name));
    return scored.slice(0, MAX_RESULTS).map((r) => r.item);
  }, [items, query]);

  useEffect(() => setCursor(0), [query]);

  const choose = (id: string) => {
    setOpen(false);
    setQuery("");
    onOpen(id);
  };

  const onInputKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => Math.min(c + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    } else if (e.key === "Enter" && results[cursor]) {
      choose(results[cursor].id);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={() => setOpen(false)}
      fullWidth
      maxWidth="sm"
      slotProps={{
        paper: { sx: { position: "fixed", top: 80, m: 0, borderRadius: 2 } },
        transition: { onEntered: () => inputRef.current?.focus() },
      }}
    >
      <Box sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: "divider" }}>
        <InputBase
          inputRef={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onInputKey}
          placeholder={t("search.placeholder")}
          fullWidth
          sx={{ fontSize: "1rem" }}
        />
      </Box>
      <Box sx={{ maxHeight: 420, overflowY: "auto" }}>
        {/*
          Until the registry has arrived, "nothing found" would be untrue: there
          is nothing to search yet. The difference is visible to the reader and
          not only to the code.
        */}
        {results.length === 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
            {loading ? t("search.loading") : t("search.empty")}
          </Typography>
        )}
        {results.map((item, i) => (
          <Box
            key={item.id}
            onMouseEnter={() => setCursor(i)}
            onClick={() => choose(item.id)}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1.5,
              px: 2,
              py: 1.1,
              cursor: "pointer",
              bgcolor: i === cursor ? "action.hover" : "transparent",
            }}
          >
            <ConfigGlyph configuration={item.configuration} size={20} />
            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
              <Typography sx={{ fontSize: "0.92rem", fontWeight: 500 }}>
                {item.name}
              </Typography>
              <Typography variant="caption">
                {t(`kind.${item.kind}`, { defaultValue: item.kind })}
              </Typography>
            </Box>
            <LevelBadge level={item.level ?? null} showScale={false} />
          </Box>
        ))}
      </Box>
      <Box
        sx={{
          px: 2, py: 1, borderTop: 1, borderColor: "divider",
          display: "flex", gap: 2, color: "text.secondary",
        }}
      >
        <Typography variant="caption" sx={{ fontFamily: MONO }}>↑↓ · Enter · Esc</Typography>
      </Box>
    </Dialog>
  );
}
