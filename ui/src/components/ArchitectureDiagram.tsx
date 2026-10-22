import { useId, useMemo, useState, type KeyboardEvent } from "react";
import { Box, Link as MuiLink, Typography, useMediaQuery } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import { getDimensionLabel, getValueLabel } from "../i18n/index";
import { MONO, stratumColor, type ThemeMode } from "../theme";
import type { ParseNote, TechDiagram } from "../api/types";

/**
 * The architecture of a technology, drawn by hand from its primary source.
 *
 * Unlike the processing path below it, this diagram is not derived from the
 * configuration: it shows the steps of the method as the work itself describes
 * them, including steps no dimension names. It is held to the record in two
 * ways. Every step names the section of the source it rests on, and a step that
 * corresponds to a dimension carries its code and value, which
 * `tests/contract/test_diagrams.py` checks against the configuration. A revised
 * reading therefore breaks the build instead of leaving a stale picture.
 *
 * A step is a button: it opens a card with the dimensions it carries, the
 * justification of each, and a link to its section. The whole step is the
 * target rather than a code inside it, because a code is a few pixels wide and
 * on a phone a finger cannot find it.
 *
 * On a narrow screen the rows become one column. Scaling the wide drawing down
 * would shrink its text below legibility.
 */

interface Props {
  diagram: TechDiagram;
  /** The justifications of the record: the card quotes them per dimension. */
  notes: ParseNote[];
  name: string;
}

export interface Frame {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Arrow {
  /** SVG path data. */
  d: string;
  /** A return to an earlier step, drawn dashed. */
  dashed: boolean;
}

export interface Layout {
  width: number;
  height: number;
  frames: Record<string, Frame>;
  arrows: Arrow[];
}

const NODE_H = 56;
const PAD = 20;
const WIDE = 680;
const NARROW = 340;
const ROW_GAP = 44;
const MIN_GAP = 24;
const MAX_GAP = 40;
const MIN_W = 84;
// Average advances of the two faces in pixels. The test environment cannot
// measure text, so widths are estimated; overflow is checked in a browser.
const TITLE_ADVANCE = 7.8;
const SUB_ADVANCE = 7.3;
const NODE_PADDING = 28;
const ARROW_GAP = 2;

function pick<T>(russian: T | undefined, english: T | undefined, lang: string): T | undefined {
  return lang === "en" ? english : russian;
}

/** The two lines of a step: its title, and its gloss, codes and section key. */
export function nodeLines(
  diagram: TechDiagram,
  id: string,
  lang: string
): { title: string; sub: string | undefined; marks: string } {
  const node = diagram.nodes[id];
  const codes = Object.keys(node.codes);
  return {
    title: pick(node.title, node.title_en, lang) ?? id,
    sub: pick(node.sub, node.sub_en, lang),
    marks: codes.length ? `${codes.join(" ")} · ${node.section}` : node.section,
  };
}

function nodeWidth(diagram: TechDiagram, id: string, lang: string): number {
  const { title, sub, marks } = nodeLines(diagram, id, lang);
  const second = (sub ? `${sub} · ` : "").length + marks.length;
  return Math.max(MIN_W, Math.ceil(Math.max(title.length * TITLE_ADVANCE, second * SUB_ADVANCE)) + NODE_PADDING);
}

function rowOf(diagram: TechDiagram, id: string): number {
  return diagram.rows.findIndex((row) => row.includes(id));
}

function broken(diagram: TechDiagram, left: string, right: string): boolean {
  return diagram.breaks.some(([a, b]) => a === left && b === right);
}

/**
 * Where every step and arrow goes.
 *
 * Rows are laid out left to right and each row is a chain, except between
 * neighbours marked as parallel branches. An edge joins a step to one in the
 * next row: straight down where the two overlap, and through the gap between
 * the rows where they do not. A loop returns to an earlier step through the gap
 * under its row, dashed. A row too wide for the drawing sends the whole diagram
 * into one column, so that no row is ever cut.
 */
export function layoutDiagram(diagram: TechDiagram, lang: string, narrow: boolean): Layout {
  const usable = WIDE - 2 * PAD;
  const widths = diagram.rows.map((row) => row.map((id) => nodeWidth(diagram, id, lang)));
  const fits = widths.every(
    (row) => row.reduce((a, b) => a + b, 0) + (row.length - 1) * MIN_GAP <= usable
  );
  return !narrow && fits ? horizontal(diagram, widths) : vertical(diagram);
}

function horizontal(diagram: TechDiagram, widths: number[][]): Layout {
  const usable = WIDE - 2 * PAD;
  const frames: Record<string, Frame> = {};
  const arrows: Arrow[] = [];
  const solid = (d: string) => arrows.push({ d, dashed: false });
  diagram.rows.forEach((row, r) => {
    const total = widths[r].reduce((a, b) => a + b, 0);
    const gap = row.length > 1 ? Math.min(MAX_GAP, (usable - total) / (row.length - 1)) : 0;
    let x = PAD;
    const y = PAD + r * (NODE_H + ROW_GAP);
    row.forEach((id, i) => {
      frames[id] = { x, y, w: widths[r][i], h: NODE_H };
      x += widths[r][i] + gap;
    });
    row.slice(1).forEach((id, i) => {
      if (broken(diagram, row[i], id)) return;
      const a = frames[row[i]];
      const b = frames[id];
      solid(`M${a.x + a.w} ${a.y + NODE_H / 2} L${b.x - ARROW_GAP} ${b.y + NODE_H / 2}`);
    });
  });
  for (const [from, to] of diagram.edges) {
    const a = frames[from];
    const b = frames[to];
    const left = Math.max(a.x, b.x);
    const right = Math.min(a.x + a.w, b.x + b.w);
    if (right - left >= 16) {
      const x = (left + right) / 2;
      solid(`M${x} ${a.y + NODE_H} L${x} ${b.y - ARROW_GAP}`);
    } else {
      const ax = a.x + a.w / 2;
      const bx = b.x + b.w / 2;
      const mid = a.y + NODE_H + ROW_GAP / 2;
      solid(`M${ax} ${a.y + NODE_H} L${ax} ${mid} L${bx} ${mid} L${bx} ${b.y - ARROW_GAP}`);
    }
  }
  // A loop leaves the step from its lower edge, runs back along the gap under
  // the row the target stands in and enters the target from below. Loops sharing
  // a gap are drawn a few pixels apart so they stay distinct.
  const inGap: Record<number, number> = {};
  for (const [from, to] of diagram.loops) {
    const a = frames[from];
    const b = frames[to];
    const band = rowOf(diagram, to);
    const k = inGap[band] ?? 0;
    inGap[band] = k + 1;
    const y = b.y + NODE_H + 10 + k * 5;
    const ax = a.x + a.w / 2 + 12;
    const bx = b.x + b.w / 2 + 12;
    const start = rowOf(diagram, from) === band ? a.y + NODE_H : a.y;
    arrows.push({
      d: `M${ax} ${start} L${ax} ${y} L${bx} ${y} L${bx} ${b.y + NODE_H + ARROW_GAP}`,
      dashed: true,
    });
  }
  const height = PAD * 2 + diagram.rows.length * NODE_H + (diagram.rows.length - 1) * ROW_GAP;
  return { width: WIDE, height, frames, arrows };
}

function vertical(diagram: TechDiagram): Layout {
  const order = diagram.rows.flat();
  const frames: Record<string, Frame> = {};
  const arrows: Arrow[] = [];
  const w = NARROW - 2 * PAD - 16;
  let y = PAD;
  order.forEach((id, i) => {
    if (i > 0) y += rowOf(diagram, id) === rowOf(diagram, order[i - 1]) ? MIN_GAP : ROW_GAP;
    frames[id] = { x: PAD, y, w, h: NODE_H };
    y += NODE_H;
  });
  const x = PAD + w / 2;
  const down = (from: string, to: string) =>
    arrows.push({ d: `M${x} ${frames[from].y + NODE_H} L${x} ${frames[to].y - ARROW_GAP}`, dashed: false });
  diagram.rows.forEach((row) =>
    row.slice(1).forEach((id, i) => {
      if (!broken(diagram, row[i], id)) down(row[i], id);
    })
  );
  let rail = 0;
  for (const [from, to] of diagram.edges) {
    if (order.indexOf(to) === order.indexOf(from) + 1) {
      down(from, to);
      continue;
    }
    // An edge that skips steps runs down a rail on the right, so it crosses
    // none of the steps in between.
    const a = frames[from];
    const b = frames[to];
    const rx = Math.min(PAD + w + 8 + rail * 5, NARROW - 3);
    rail += 1;
    arrows.push({
      d: `M${a.x + w} ${a.y + NODE_H / 2} L${rx} ${a.y + NODE_H / 2} L${rx} ${b.y + NODE_H / 2} L${b.x + w + ARROW_GAP} ${b.y + NODE_H / 2}`,
      dashed: false,
    });
  }
  // Loops climb back up a rail on the left.
  let back = 0;
  for (const [from, to] of diagram.loops) {
    const a = frames[from];
    const b = frames[to];
    const lx = Math.max(PAD - 8 - back * 5, 3);
    back += 1;
    arrows.push({
      d: `M${a.x} ${a.y + NODE_H / 2} L${lx} ${a.y + NODE_H / 2} L${lx} ${b.y + NODE_H / 2} L${b.x - ARROW_GAP} ${b.y + NODE_H / 2}`,
      dashed: true,
    });
  }
  return { width: NARROW, height: y + PAD, frames, arrows };
}

export function ArchitectureDiagram({ diagram, notes, name }: Props) {
  const theme = useTheme();
  const mode = theme.palette.mode as ThemeMode;
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const narrow = useMediaQuery(theme.breakpoints.down("sm"));
  const marker = useId().replace(/:/g, "");
  const [selected, setSelected] = useState<string | null>(null);

  const layout = useMemo(() => layoutDiagram(diagram, lang, narrow), [diagram, lang, narrow]);
  const order = diagram.rows.flat();
  const sections = Object.fromEntries(diagram.sections.map((s) => [s.key, s]));

  const toggle = (id: string) => setSelected((current) => (current === id ? null : id));
  const onKey = (id: string) => (event: KeyboardEvent<SVGGElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggle(id);
    }
  };

  const chosen = selected ? diagram.nodes[selected] : null;

  return (
    <Box>
      <Box
        component="svg"
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        role="group"
        aria-label={`${t("architecture.title")}: ${name}`}
        sx={{
          display: "block",
          width: "100%",
          maxWidth: layout.width,
          height: "auto",
          "& g[role=button]": { cursor: "pointer", outline: "none" },
          "& g[role=button]:focus-visible rect[data-frame]": {
            stroke: theme.palette.primary.main,
            strokeWidth: 2,
          },
        }}
      >
        <title>{name}</title>
        <desc>{order.map((id) => nodeLines(diagram, id, lang).title).join(", ")}</desc>
        <defs>
          <marker
            id={marker}
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path
              d="M2 1L8 5L2 9"
              fill="none"
              stroke={theme.palette.text.secondary}
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </marker>
        </defs>
        {layout.arrows.map((arrow, i) => (
          <path
            key={i}
            d={arrow.d}
            fill="none"
            stroke={theme.palette.text.secondary}
            strokeWidth={1}
            strokeDasharray={arrow.dashed ? "4 3" : undefined}
            data-loop={arrow.dashed ? "" : undefined}
            markerEnd={`url(#${marker})`}
          />
        ))}
        {order.map((id) => {
          const f = layout.frames[id];
          const node = diagram.nodes[id];
          const codes = Object.keys(node.codes);
          const { title, sub, marks } = nodeLines(diagram, id, lang);
          const active = selected === id;
          return (
            <g
              key={id}
              role="button"
              tabIndex={0}
              aria-pressed={active}
              aria-label={[title, sub, marks].filter(Boolean).join(", ")}
              data-node={id}
              data-codes={codes.join(" ")}
              onClick={() => toggle(id)}
              onKeyDown={onKey(id)}
            >
              <rect
                data-frame=""
                x={f.x}
                y={f.y}
                width={f.w}
                height={f.h}
                rx={4}
                fill={theme.palette.background.paper}
                stroke={active ? theme.palette.primary.main : theme.palette.divider}
                strokeWidth={active ? 1.5 : 1}
              />
              {codes.length > 0 && (
                <rect
                  x={f.x + 0.5}
                  y={f.y + 0.5}
                  width={4}
                  height={f.h - 1}
                  fill={stratumColor(codes[0][0], mode)}
                />
              )}
              <text
                x={f.x + f.w / 2}
                y={f.y + 20}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={14}
                fontWeight={500}
                fill={theme.palette.text.primary}
              >
                {title}
              </text>
              <text
                x={f.x + f.w / 2}
                y={f.y + 38}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={12}
                fill={theme.palette.text.secondary}
              >
                {sub && <tspan>{`${sub} · `}</tspan>}
                <tspan fontFamily={MONO}>{marks}</tspan>
              </text>
            </g>
          );
        })}
      </Box>

      <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 1 }}>
        {t("architecture.source")}:{" "}
        <MuiLink href={diagram.source.url} target="_blank" rel="noopener noreferrer">
          {diagram.source.label}
        </MuiLink>
        {diagram.sections.map((s) => (
          <span key={s.key}>
            {" · "}
            <Box component="span" sx={{ fontFamily: MONO }}>{s.key}</Box>{" "}
            <MuiLink href={s.url} target="_blank" rel="noopener noreferrer">
              {s.title}
            </MuiLink>
          </span>
        ))}
      </Typography>

      {diagram.loops.length > 0 && (
        <Typography variant="caption" color="text.secondary" component="p">
          {t("architecture.loop")}
        </Typography>
      )}

      {chosen && selected && (
        <Box
          data-testid="architecture-card"
          sx={{ mt: 1.5, p: 1.5, border: 1, borderColor: "divider", borderRadius: 1 }}
        >
          <Typography variant="subtitle2">{nodeLines(diagram, selected, lang).title}</Typography>
          {pick(chosen.note, chosen.note_en, lang) && (
            <Typography variant="body2" sx={{ mt: 0.5 }}>
              {pick(chosen.note, chosen.note_en, lang)}
            </Typography>
          )}
          {Object.entries(chosen.codes).map(([code, value]) => {
            const note = notes.find((n) => n.code === code && (!n.to || n.to === value));
            const why = note ? pick(note.did, note.did_en, lang) : undefined;
            return (
              <Box key={code} sx={{ mt: 1 }}>
                <Typography variant="body2">
                  <Box component="span" sx={{ fontFamily: MONO, color: "text.secondary", mr: 1 }}>
                    {code}
                  </Box>
                  {getDimensionLabel(code, lang)?.name ?? code}:{" "}
                  <Box component="span" sx={{ fontWeight: 500 }}>
                    {getValueLabel(code, value, lang) ?? value}
                  </Box>
                </Typography>
                {why && (
                  <Typography variant="caption" color="text.secondary" component="p">
                    {why}
                  </Typography>
                )}
              </Box>
            );
          })}
          {chosen.residual && (() => {
            // A residual is a decision of the reading as much as a code is, so the
            // card shows it the same way: what the schema cannot say, then why.
            const note = notes.find((n) => n.residual === chosen.residual);
            const term = pick(note?.residual_term ?? undefined, note?.residual_term_en ?? undefined, lang);
            const why = note ? pick(note.did, note.did_en, lang) : undefined;
            return (
              <Box sx={{ mt: 1 }} data-testid="architecture-residual">
                <Typography variant="body2">
                  {t("architecture.residual")}:{" "}
                  <Box component="span" sx={{ fontWeight: 500 }}>{term ?? chosen.residual}</Box>
                </Typography>
                {why && (
                  <Typography variant="caption" color="text.secondary" component="p">
                    {why}
                  </Typography>
                )}
              </Box>
            );
          })()}
          {sections[chosen.section] && (
            <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 1 }}>
              {t("architecture.section")}:{" "}
              <MuiLink href={sections[chosen.section].url} target="_blank" rel="noopener noreferrer">
                {sections[chosen.section].title}
              </MuiLink>
            </Typography>
          )}
        </Box>
      )}
    </Box>
  );
}
