import { Box, Link } from "@mui/material";
import type { ReactNode } from "react";

// Парсит текст с разметкой:
// [N] — citation, кликабельная ссылка на #ref-N
// [Name](url) — inline-ссылка на ресурс
// \n\n — новый абзац
// Возвращает массив ReactNode.

const CITATION_RE = /\[(\d+(?:\s*,\s*\d+)*)\]/g;
const LINK_RE = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;

interface Props {
  children: string;
  sx?: object;
}

export function RichText({ children, sx }: Props) {
  const paragraphs = children.split("\n\n");
  return (
    <Box sx={sx}>
      {paragraphs.map((para, pi) => (
        <Box key={pi} component="p" sx={{ mb: 1.5, lineHeight: 1.8 }}>
          {renderInline(para, `p${pi}`)}
        </Box>
      ))}
    </Box>
  );
}

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  // Сначала найдём все inline-ссылки [Name](url) и citations [N],
  // затем соберём части.
  type Token = { type: "text"; value: string } | { type: "link"; label: string; url: string } | { type: "cite"; ids: string[] };
  const tokens: Token[] = [];
  let i = 0;
  let key = 0;

  // Комбинированный regex: ищет [Name](url) или [N] или [N, M]
  const combined = /\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)|\[(\d+(?:\s*,\s*\d+)*)\]/g;
  let lastIdx = 0;
  let m: RegExpExecArray | null;

  while ((m = combined.exec(text)) !== null) {
    if (m.index > lastIdx) {
      tokens.push({ type: "text", value: text.slice(lastIdx, m.index) });
    }
    if (m[1] !== undefined && m[2] !== undefined) {
      // Inline-ссылка [Name](url)
      tokens.push({ type: "link", label: m[1], url: m[2] });
    } else if (m[3] !== undefined) {
      // Citation [N] или [N, M]
      const ids = m[3].split(",").map((s) => s.trim());
      tokens.push({ type: "cite", ids });
    }
    lastIdx = combined.lastIndex;
  }
  if (lastIdx < text.length) {
    tokens.push({ type: "text", value: text.slice(lastIdx) });
  }

  // Рендерим токены.
  const nodes: ReactNode[] = [];
  for (const tok of tokens) {
    if (tok.type === "text") {
      nodes.push(<span key={`${keyPrefix}-t${key++}`}>{tok.value}</span>);
    } else if (tok.type === "link") {
      nodes.push(
        <Link key={`${keyPrefix}-l${key++}`} href={tok.url} target="_blank" rel="noopener" sx={{ fontWeight: 500 }}>
          {tok.label}
        </Link>
      );
    } else if (tok.type === "cite") {
      nodes.push(
        <span key={`${keyPrefix}-c${key++}`} style={{ whiteSpace: "nowrap" }}>
          {tok.ids.map((id, idx) => (
            <span key={idx}>
              {idx > 0 && ", "}
              <Link
                href={`#ref-${id}`}
                onClick={(e) => {
                  e.preventDefault();
                  document.getElementById(`ref-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
                }}
                sx={{ fontWeight: 500, cursor: "pointer" }}
              >
                [{id}]
              </Link>
            </span>
          ))}
        </span>
      );
    }
  }
  return nodes;
}
