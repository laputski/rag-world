import { Box, Typography } from "@mui/material";
import { MONO } from "../theme";

/**
 * Колонка фасетов со счётчиками.
 *
 * У каждого значения стоит число записей: без него читатель не знает, приведёт
 * ли отбор к трём записям или к тридцати, и вынужден выяснять это нажатием.
 * Значение без записей показывается приглушённым и не выбирается — предлагать
 * заведомо пустой отбор нечестно.
 */

export interface FacetOption {
  value: string;
  label: string;
  count: number;
  /** Необязательный элемент слева: метка страты, значок рода объекта. */
  icon?: React.ReactNode;
}

interface Props {
  title: string;
  options: FacetOption[];
  selected: string;
  onSelect: (value: string) => void;
  /** Подпись пункта «все значения». */
  allLabel: string;
  totalCount: number;
}

export function FacetRail({
  title, options, selected, onSelect, allLabel, totalCount,
}: Props) {
  const rows: FacetOption[] = [
    { value: "", label: allLabel, count: totalCount },
    ...options,
  ];

  return (
    <Box sx={{ mb: 3 }}>
      <Typography
        variant="caption"
        sx={{
          display: "block",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          fontWeight: 600,
          mb: 1,
        }}
      >
        {title}
      </Typography>
      {rows.map((option) => {
        const active = option.value === selected;
        const empty = option.count === 0 && option.value !== "";
        return (
          <Box
            key={option.value || "__all"}
            onClick={() => !empty && onSelect(option.value)}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 0.75,
              py: 0.4,
              cursor: empty ? "default" : "pointer",
              opacity: empty ? 0.4 : 1,
              color: active ? "text.primary" : "text.secondary",
              fontWeight: active ? 600 : 400,
              fontSize: "0.85rem",
              "&:hover": { color: empty ? "text.secondary" : "text.primary" },
            }}
          >
            {option.icon}
            <Box component="span" sx={{ flexGrow: 1, minWidth: 0 }}>
              {option.label}
            </Box>
            <Box
              component="span"
              className="tabular"
              sx={{ fontFamily: MONO, fontSize: "0.75rem", color: "text.secondary" }}
            >
              {option.count}
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}
