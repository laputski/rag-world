import { Box, Link } from "@mui/material";
import type { ReactNode } from "react";

// Matches [1], [12], [1, 2], [1,2,3] — citation groups in article text.
const CITATION_RE = /\[(\d+(?:\s*,\s*\d+)*)\]/g;

interface Props {
  children: string;
  component?: ReactNode;
  sx?: object;
}

/**
 * Renders a text string, turning [N] citation markers into clickable links.
 * Clicking scrolls to the SPECIFIC reference entry #ref-N (not just the section).
 * Multi-citations like [1, 2] produce individual links to ref-1 and ref-2.
 */
export function CitationText({ children, component = "p", sx }: Props) {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  CITATION_RE.lastIndex = 0;
  while ((match = CITATION_RE.exec(children)) !== null) {
    if (match.index > lastIndex) {
      parts.push(children.slice(lastIndex, match.index));
    }
    const ids = match[1].split(",").map((s) => s.trim());
    // Render each citation id as a separate link to its specific #ref-N anchor.
    const links: ReactNode[] = [];
    ids.forEach((id, i) => {
      links.push(
        <Link
          key={`cite-${key}-${i}`}
          href={`#ref-${id}`}
          onClick={(e) => {
            e.preventDefault();
            document.getElementById(`ref-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
          }}
          sx={{ fontWeight: 500, cursor: "pointer" }}
        >
          [{id}]
        </Link>
      );
      if (i < ids.length - 1) links.push(", ");
    });
    parts.push(<span key={`cite-group-${key++}`}>[{links}]</span>);

    // Simplify: render as [1], [2] individual links without extra brackets
    parts.pop();
    parts.push(
      <span key={`cite-group-${key++}`} style={{ whiteSpace: "nowrap" }}>
        {ids.map((id, i) => (
          <span key={i}>
            {i > 0 && ", "}
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

    lastIndex = CITATION_RE.lastIndex;
  }
  if (lastIndex < children.length) {
    parts.push(children.slice(lastIndex));
  }

  return (
    <Box component={component as React.ElementType} sx={sx}>
      {parts}
    </Box>
  );
}
