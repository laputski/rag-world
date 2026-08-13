import { useEffect, useMemo, useState } from "react";
import { Alert, Box, CircularProgress, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getRegistry } from "../api/client";
import { FacetRail, type FacetOption } from "../components/FacetRail";
import { FeedRow, type FeedItem } from "../components/FeedRow";
import { StratumChip } from "../components/StratumChip";
import { STRATA } from "../schema.generated";
import { useDocumentHead } from "../useDocumentHead";

/**
 * Реестр технологий: фасеты слева, лента по центру.
 *
 * Данные читаются одним артефактом, отбор и сортировка идут на клиенте: при
 * нескольких сотнях записей это отвечает мгновенно и не требует сервера.
 * Состояние отбора живёт в адресе страницы, поэтому результат можно
 * процитировать ссылкой — для читателя-исследователя это важнее удобства.
 */

/**
 * Порядок родов при показе. Сам перечень берётся из данных, а этот список
 * задаёт лишь очерёдность: от самого общего к самому частному.
 *
 * Записанный руками перечень разошёлся с данными в обе стороны сразу. Род
 * «артефакт оценки» стоял в отборе с нулём записей, потому что таких записей
 * в реестре нет; род «атака» из отбора выпал, хотя записи есть, и добраться
 * до них отбором было нельзя. Поэтому перечень выводится, а не пишется.
 */
const KIND_ORDER = ["paradigm", "architecture", "technique", "tool", "attack", "artifact"];
const SORTS = ["level", "attention", "recent", "name"] as const;
type Sort = (typeof SORTS)[number];

const LEVEL_ORDER = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"];

export function RegistryPage() {

  const { t } = useTranslation();
  useDocumentHead({
    title: t("head.registry.title"),
    description: t("head.registry.description"),
  });
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [all, setAll] = useState<FeedItem[]>([]);
  const [builtAt, setBuiltAt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const kind = params.get("kind") ?? "";
  const stratum = params.get("stratum") ?? "";
  const sort = (params.get("sort") as Sort) ?? "level";

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  useEffect(() => {
    setLoading(true);
    getRegistry()
      .then((res) => {
        setAll(res.technologies as unknown as FeedItem[]);
        setBuiltAt(res.built_at);
        setError(null);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const items = useMemo(() => {
    const filtered = all.filter(
      (it) => (!kind || it.kind === kind) && (!stratum || it.groups.includes(stratum))
    );
    const sorted = [...filtered];
    if (sort === "level") {
      // Записи без уровня уходят вниз: отсутствие данных не должно
      // конкурировать за внимание с подтверждёнными уровнями.
      sorted.sort((a, b) =>
        (b.level ? LEVEL_ORDER.indexOf(b.level) : -1) -
        (a.level ? LEVEL_ORDER.indexOf(a.level) : -1) ||
        a.name.localeCompare(b.name));
    } else if (sort === "attention") {
      sorted.sort((a, b) => (b.attention ?? -1) - (a.attention ?? -1));
    } else if (sort === "recent") {
      sorted.sort((a, b) =>
        (b.first_published ?? "").localeCompare(a.first_published ?? ""));
    } else {
      sorted.sort((a, b) => a.name.localeCompare(b.name));
    }
    return sorted;
  }, [all, kind, stratum, sort]);

  // Роды берутся из самих записей: отбор по роду, которого в реестре нет,
  // предлагать нечего, а род, появившийся в данных, попадает в отбор сам.
  const kindFacets: FacetOption[] = useMemo(() => {
    const present = new Set(all.map((it) => it.kind).filter(Boolean));
    const ordered = [
      ...KIND_ORDER.filter((k) => present.has(k)),
      ...[...present].filter((k) => !KIND_ORDER.includes(k)).sort(),
    ];
    return ordered.map((k) => ({
      value: k,
      label: t(`kind.${k}`, { defaultValue: k }),
      count: all.filter((it) => it.kind === k && (!stratum || it.groups.includes(stratum))).length,
    }));
  }, [all, stratum, t]);

  const stratumFacets: FacetOption[] = STRATA.map((s) => ({
    value: s.code,
    label: t(`stratum.${s.code}`, { defaultValue: s.name }).replace(/^[A-G]\.\s*/, ""),
    count: all.filter((it) => it.groups.includes(s.code) && (!kind || it.kind === kind)).length,
    icon: <StratumChip stratum={s.code} />,
  }));

  return (
    <Box sx={{ display: "flex", gap: 4, alignItems: "flex-start" }}>
      <Box sx={{ width: 210, flexShrink: 0, display: { xs: "none", md: "block" }, position: "sticky", top: 76 }}>
        <FacetRail
          title={t("registry.filterKind")}
          options={kindFacets}
          selected={kind}
          onSelect={(v) => setParam("kind", v)}
          allLabel={t("registry.all")}
          totalCount={all.length}
        />
        <FacetRail
          title={t("registry.filterGroup")}
          options={stratumFacets}
          selected={stratum}
          onSelect={(v) => setParam("stratum", v)}
          allLabel={t("registry.all")}
          totalCount={all.length}
        />
      </Box>

      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <Typography variant="h2" sx={{ mb: 0.5 }}>{t("registry.title")}</Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 2, maxWidth: 720 }}>
          {t("registry.subtitle")}
        </Typography>

        <Box
          sx={{
            display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap",
            py: 1, borderBottom: 1, borderColor: "divider", mb: 1,
          }}
        >
          {SORTS.map((s) => (
            <Typography
              key={s}
              onClick={() => setParam("sort", s)}
              sx={{
                fontSize: "0.82rem", cursor: "pointer",
                color: sort === s ? "text.primary" : "text.secondary",
                fontWeight: sort === s ? 600 : 400,
              }}
            >
              {t(`registry.sort.${s}`)}
            </Typography>
          ))}
          <Typography variant="caption" className="tabular" sx={{ ml: "auto" }}>
            {items.length} {t("registry.total")}
            {builtAt && ` · ${t("common.builtAt")} ${new Date(builtAt).toLocaleDateString()}`}
          </Typography>
        </Box>

        {error && <Alert severity="info" sx={{ mb: 2 }}>{t("registry.unavailable")}</Alert>}
        {loading && <CircularProgress sx={{ display: "block", mx: "auto", my: 6 }} />}

        {!loading && !error && items.map((item) => (
          <FeedRow key={item.id} item={item} onOpen={(id) => navigate(`/tech/${id}`)} />
        ))}
      </Box>
    </Box>
  );
}
