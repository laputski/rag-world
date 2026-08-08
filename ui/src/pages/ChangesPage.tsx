import { useEffect, useMemo, useState } from "react";
import { Alert, Box, CircularProgress, Link as MuiLink, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getChanges } from "../api/client";
import type { RegistryChange } from "../api/types";
import { MONO } from "../theme";

/**
 * Хроника изменений реестра.
 *
 * Свежесть портала доказывается не датой сборки, а перечнем произошедшего.
 * Поэтому у каждой записи хроники указаны прежний и новый уровень и те
 * свидетельства, которые к изменению привели: утверждение об изменении без
 * основания ничем не лучше отсутствия хроники.
 */

const WINDOWS = [
  { key: "week", days: 7 },
  { key: "month", days: 31 },
  { key: "all", days: 0 },
] as const;

export function ChangesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [changes, setChanges] = useState<RegistryChange[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const window = params.get("window") ?? "month";

  useEffect(() => {
    getChanges()
      .then((res) => { setChanges(res.changes); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const visible = useMemo(() => {
    const days = WINDOWS.find((w) => w.key === window)?.days ?? 0;
    if (!days) return changes;
    const since = new Date();
    since.setDate(since.getDate() - days);
    return changes.filter((c) => new Date(c.changed_at) >= since);
  }, [changes, window]);

  return (
    <Box sx={{ maxWidth: 900 }}>
      <Typography variant="h2" sx={{ mb: 0.5 }}>{t("changes.title")}</Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
        {t("changes.subtitle")}
      </Typography>

      <Box sx={{
        display: "flex", gap: 2.5, py: 1, mb: 1,
        borderTop: 1, borderBottom: 1, borderColor: "divider",
      }}>
        {WINDOWS.map((w) => (
          <Typography
            key={w.key}
            onClick={() => {
              const next = new URLSearchParams(params);
              next.set("window", w.key);
              setParams(next, { replace: true });
            }}
            sx={{
              fontSize: "0.85rem", cursor: "pointer",
              color: window === w.key ? "text.primary" : "text.secondary",
              fontWeight: window === w.key ? 600 : 400,
            }}
          >
            {t(`changes.window.${w.key}`)}
          </Typography>
        ))}
        <Typography variant="caption" className="tabular" sx={{ ml: "auto" }}>
          {visible.length}
        </Typography>
      </Box>

      {error && <Alert severity="info">{t("changes.unavailable")}</Alert>}
      {loading && <CircularProgress sx={{ display: "block", mx: "auto", my: 6 }} />}
      {!loading && !error && visible.length === 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>
          {t("changes.empty")}
        </Typography>
      )}

      {visible.map((change, i) => (
        <Box
          key={`${change.technology_id}-${change.changed_at}-${i}`}
          sx={{ py: 1.5, borderBottom: 1, borderColor: "divider" }}
        >
          <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.5, flexWrap: "wrap" }}>
            <MuiLink
              href={`/tech/${change.technology_id}`}
              onClick={(e) => { e.preventDefault(); navigate(`/tech/${change.technology_id}`); }}
              sx={{ color: "text.primary", fontWeight: 600 }}
            >
              {change.name}
            </MuiLink>
            <Typography sx={{ fontFamily: MONO, fontSize: "0.85rem" }}>
              {change.level_before ?? "—"} → {change.level_after}
            </Typography>
            <Typography variant="caption">
              {t(`changes.${change.kind === "level_up" ? "levelUp"
                : change.kind === "level_down" ? "levelDown" : "added"}`)}
            </Typography>
            <Typography variant="caption" className="tabular" sx={{ ml: "auto" }}>
              {change.changed_at}
            </Typography>
          </Box>

          {change.evidence.length > 0 && (
            <Box sx={{ mt: 0.75, pl: 0 }}>
              <Typography variant="caption" sx={{ display: "block", mb: 0.25 }}>
                {t("changes.basis")}
              </Typography>
              {change.evidence.slice(0, 4).map((e, j) => (
                <Typography key={j} variant="caption" sx={{ display: "block", color: "text.secondary" }}>
                  {e.type}
                  {e.source && (
                    <>
                      {" · "}
                      <MuiLink href={e.source} target="_blank" rel="noopener">
                        {e.source.replace(/^https?:\/\//, "").slice(0, 60)}
                      </MuiLink>
                    </>
                  )}
                </Typography>
              ))}
              {change.evidence.length > 4 && (
                <Typography variant="caption" color="text.secondary">
                  {t("changes.more", { count: change.evidence.length - 4 })}
                </Typography>
              )}
            </Box>
          )}
        </Box>
      ))}
    </Box>
  );
}
