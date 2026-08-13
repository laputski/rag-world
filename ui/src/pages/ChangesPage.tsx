import { useEffect, useMemo, useState } from "react";
import {
  Alert, Box, Chip, CircularProgress, Collapse, Link as MuiLink, Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getChanges } from "../api/client";
import type { RegistryChange } from "../api/types";
import { MONO } from "../theme";
import { useDocumentHead } from "../useDocumentHead";

/**
 * Хроника изменений реестра.
 *
 * Свежесть портала доказывается не датой сборки, а перечнем произошедшего.
 * Поэтому у каждой записи хроники указаны прежний и новый уровень и те
 * свидетельства, которые к изменению привели: утверждение об изменении без
 * основания ничем не лучше отсутствия хроники.
 *
 * Порядок показа исходит из того, как страницу читают. Сперва читатель хочет
 * знать, много ли произошло и было ли среди этого понижение, и лишь потом
 * разбирает отдельные записи. Поэтому наверху стоит счёт по родам изменений, а
 * записи собраны по датам: восемьдесят семь строк с повторённой в каждой датой
 * читались как однородная простыня, тогда как четыре даты с числом изменений
 * при каждой видны сразу.
 *
 * Основания свёрнуты. Они обязаны быть доступны, иначе изменение
 * недоказуемо, но в развёрнутом виде занимали больше места, чем само
 * изменение, и вытесняли его. Развернуть их можно одним щелчком, и в
 * свёрнутом виде сказано, сколько их и какого они рода.
 */

const WINDOWS = [
  { key: "week", days: 7 },
  { key: "month", days: 31 },
  { key: "all", days: 0 },
] as const;

/** Роды изменений в порядке важности: понижение читается первым. */
const KINDS = ["level_down", "level_up", "added"] as const;

const KIND_LABEL: Record<string, string> = {
  level_up: "changes.levelUp",
  level_down: "changes.levelDown",
  added: "changes.added",
};

/**
 * Цвет рода изменения.
 *
 * Понижение — единственное событие портала, которое означает, что прежнее
 * утверждение оказалось неверным, и увидеть его нужно раньше всего
 * остального. Повышение и появление записи привычны и цветом не выделяются.
 */
function kindColor(kind: string): "warning.main" | "text.secondary" {
  return kind === "level_down" ? "warning.main" : "text.secondary";
}

export function ChangesPage() {

  const { t } = useTranslation();
  useDocumentHead({
    title: t("head.changes.title"),
    description: t("head.changes.description"),
  });
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

  /** Счёт по родам изменений за выбранный период. */
  const tally = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const change of visible) counts[change.kind] = (counts[change.kind] ?? 0) + 1;
    return KINDS.filter((kind) => counts[kind]).map((kind) => ({ kind, count: counts[kind] }));
  }, [visible]);

  /** Изменения, собранные по датам, свежие дни сверху. */
  const byDate = useMemo(() => {
    const groups = new Map<string, RegistryChange[]>();
    for (const change of visible) {
      const day = groups.get(change.changed_at) ?? [];
      day.push(change);
      groups.set(change.changed_at, day);
    }
    return [...groups.entries()]
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([date, items]) => ({
        date,
        // Внутри дня понижения идут первыми по той же причине, по какой они
        // выделены цветом: это единственное, что читатель обязан заметить.
        items: [...items].sort(
          (a, b) => KINDS.indexOf(a.kind as never) - KINDS.indexOf(b.kind as never)
        ),
      }));
  }, [visible]);

  return (
    <Box sx={{ maxWidth: 900 }}>
      <Typography variant="h2" sx={{ mb: 0.5 }}>{t("changes.title")}</Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
        {t("changes.subtitle")}
      </Typography>

      <Box sx={{
        display: "flex", gap: 2.5, py: 1,
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
      </Box>

      {/*
        Счёт по родам стоит до записей и отвечает на вопрос, с которым на
        страницу приходят: много ли произошло и есть ли среди этого понижение.
        Без него ответ требовал пролистать всю хронику.
      */}
      {!loading && !error && visible.length > 0 && (
        <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap", py: 1.5 }}>
          {tally.map(({ kind, count }) => (
            <Box key={kind}>
              <Typography
                className="tabular"
                sx={{ fontSize: "1.5rem", lineHeight: 1.1, color: kindColor(kind) === "warning.main" ? "warning.main" : "text.primary" }}
              >
                {count}
              </Typography>
              <Typography variant="caption" sx={{ color: kindColor(kind) }}>
                {t(KIND_LABEL[kind])}
              </Typography>
            </Box>
          ))}
          <Box sx={{ ml: "auto", textAlign: "right" }}>
            <Typography className="tabular" sx={{ fontSize: "1.5rem", lineHeight: 1.1 }}>
              {byDate.length}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {t("changes.daysWithChanges", { count: byDate.length })}
            </Typography>
          </Box>
        </Box>
      )}

      {error && <Alert severity="info">{t("changes.unavailable")}</Alert>}
      {loading && <CircularProgress sx={{ display: "block", mx: "auto", my: 6 }} />}
      {!loading && !error && visible.length === 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>
          {t("changes.empty")}
        </Typography>
      )}

      {byDate.map(({ date, items }) => (
        <Box key={date} sx={{ mt: 3 }}>
          <Box sx={{
            display: "flex", alignItems: "baseline", gap: 1.5,
            borderBottom: 1, borderColor: "divider", pb: 0.5, mb: 0.5,
          }}>
            <Typography className="tabular" sx={{ fontWeight: 600, fontSize: "0.95rem" }}>
              {date}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {t("changes.thatDay", { count: items.length })}
            </Typography>
          </Box>
          {items.map((change, i) => (
            <ChangeRow key={`${change.technology_id}-${i}`} change={change} onOpen={navigate} />
          ))}
        </Box>
      ))}
    </Box>
  );
}

/**
 * Одна строка хроники: что за запись, как изменился уровень и на чём это стоит.
 *
 * Переход уровня набран моноширинным и стоит сразу за именем, потому что
 * ровно он и есть содержание строки. Прежний уровень у новой записи не
 * показывается вовсе: прочерк на его месте читался как «был нулевой».
 */
function ChangeRow({
  change, onOpen,
}: {
  change: RegistryChange;
  onOpen: (path: string) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const added = change.kind === "added";

  return (
    <Box sx={{ py: 0.75, borderBottom: 1, borderColor: "divider" }}>
      <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.5, flexWrap: "wrap" }}>
        {change.kind === "level_down" && (
          <Chip
            size="small"
            label={t("changes.levelDown")}
            sx={{ height: 20, color: "warning.main", borderColor: "warning.main" }}
            variant="outlined"
          />
        )}
        <MuiLink
          href={`/tech/${change.technology_id}`}
          onClick={(e) => { e.preventDefault(); onOpen(`/tech/${change.technology_id}`); }}
          sx={{ color: "text.primary", fontWeight: 600 }}
        >
          {change.name}
        </MuiLink>
        <Typography
          sx={{
            fontFamily: MONO, fontSize: "0.85rem",
            color: change.kind === "level_down" ? "warning.main" : "text.primary",
          }}
        >
          {added
            ? t("changes.appearedAt", { level: change.level_after })
            : `${change.level_before} → ${change.level_after}`}
        </Typography>

        {change.evidence.length > 0 && (
          <MuiLink
            component="button"
            onClick={() => setOpen((v) => !v)}
            sx={{ ml: "auto", fontSize: "0.75rem" }}
          >
            {open
              ? t("changes.hideBasis")
              : t("changes.basisCount", { count: change.evidence.length })}
          </MuiLink>
        )}
      </Box>

      <Collapse in={open}>
        <Box sx={{ mt: 0.75, pl: 1.5, borderLeft: 2, borderColor: "divider" }}>
          {change.evidence.map((e, j) => (
            <Typography key={j} variant="caption" sx={{ display: "block", color: "text.secondary" }}>
              {e.type}
              {e.source && (
                <>
                  {" · "}
                  <MuiLink href={e.source} target="_blank" rel="noopener">
                    {/*
                      Показывается имя источника, а не весь адрес.
                      `openalex.org/W4400373146` не сообщает читателю ничего
                      сверх `openalex.org`, а места занимает вчетверо больше.
                    */}
                    {hostOf(e.source)}
                  </MuiLink>
                </>
              )}
            </Typography>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url.replace(/^https?:\/\//, "").split("/")[0];
  }
}
