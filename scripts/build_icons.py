#!/usr/bin/env python3
"""The portal's icons: the tab file, the device icon, the link preview image.

The mark is drawn in code, in `ui/src/components/Logo.tsx`, and the icons are
needed as files: a browser tab, a home-screen icon and a link preview are read
by platforms that do not run the portal's code. Hence the task — obtain the same
cells as files without keeping a second description of the mark.

The pattern and the colours are therefore **read out of the interface sources**
rather than copied here. The parsing is narrow and checkable: if it does not
find seven strata or twenty-eight cells, the build stops. A divergence is made
loud that way, whereas a hand-copied drawing would diverge in silence and be
discovered on somebody else's link preview.

The raster is written by hand over `zlib`: the mark consists of rectangles, and
drawing them into a pixel buffer is simpler than taking a dependency on a vector
graphics renderer for the sake of fourteen squares.

Usage::

    python3 scripts/build_icons.py
    python3 scripts/build_icons.py --check   # check without building
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "ui" / "src" / "theme.ts"
LOGO = ROOT / "ui" / "src" / "components" / "Logo.tsx"
PUBLIC = ROOT / "ui" / "public"

STRATA = ["A", "B", "C", "D", "E", "F", "G"]
ROWS = 4

#: The strata and rows of the compact drawing. They are kept in step with
#: `Logo.tsx` by `tests/contract/test_icons_match_the_logo.py`.
COMPACT_STRATA = ["A", "C", "E", "G"]
COMPACT_ROWS = 3

#: The portal's neutral colours, used for the grounds. There are few, and they
#: come from the same place as the rest.
NEUTRAL_RE = re.compile(
    r"(?P<mode>light|dark):\s*\{\s*bg:\s*\"(?P<bg>#[0-9A-Fa-f]{6})\""
)


def _strata_colors() -> dict[str, dict[str, str]]:
    """The stratum colours from `theme.ts`, per theme."""
    text = THEME.read_text(encoding="utf-8")
    block = re.search(
        r"STRATUM_COLORS[^=]*=\s*\{(?P<body>.*?)\n\};", text, re.S
    )
    if not block:
        raise SystemExit("theme.ts declares no stratum colours")

    out: dict[str, dict[str, str]] = {}
    for mode in ("light", "dark"):
        section = re.search(
            rf"{mode}:\s*\{{(?P<body>.*?)\}},", block.group("body"), re.S
        )
        if not section:
            raise SystemExit(f"theme.ts has no palette for the {mode} theme")
        found = dict(re.findall(r"([A-G]):\s*\"(#[0-9A-Fa-f]{6})\"", section.group("body")))
        missing = [s for s in STRATA if s not in found]
        if missing:
            raise SystemExit(f"the {mode} palette lacks the strata {missing}")
        out[mode] = found
    return out


def _backgrounds() -> dict[str, str]:
    text = THEME.read_text(encoding="utf-8")
    found = {m.group("mode"): m.group("bg") for m in NEUTRAL_RE.finditer(text)}
    missing = [mode for mode in ("light", "dark") if mode not in found]
    if missing:
        raise SystemExit(f"theme.ts has no background for the themes {missing}")
    return found


def _pattern() -> dict[str, list[bool]]:
    """The pattern of the mark, read from `Logo.tsx`."""
    text = LOGO.read_text(encoding="utf-8")
    block = re.search(r"PATTERN[^=]*=\s*\{(?P<body>.*?)\n\};", text, re.S)
    if not block:
        raise SystemExit("Logo.tsx declares no pattern for the mark")
    out: dict[str, list[bool]] = {}
    for stratum, body in re.findall(r"([A-G]):\s*\[(.*?)\]", block.group("body"), re.S):
        out[stratum] = [value.strip() == "true" for value in body.split(",")]
    missing = [s for s in STRATA if s not in out]
    if missing:
        raise SystemExit(f"the pattern lacks the strata {missing}")
    wrong = {s: len(v) for s, v in out.items() if len(v) != ROWS}
    if wrong:
        raise SystemExit(f"the pattern has rows other than {ROWS}: {wrong}")
    return out


def cells(size: float, compact: bool) -> list[tuple[float, float, float, str]]:
    """The cells of the mark: x, y, side, stratum code."""
    pattern = _pattern()
    strata = COMPACT_STRATA if compact else STRATA
    rows = COMPACT_ROWS if compact else ROWS
    step = size / rows
    gap = step * (0.16 if compact else 0.2)
    side = step - gap
    out = []
    for col, stratum in enumerate(strata):
        for row in range(rows):
            if pattern[stratum][row]:
                out.append((col * step, row * step, side, stratum))
    return out


def render_favicon() -> str:
    """The tab icon: one file that changes palette with the browser theme.

    A raster icon cannot do that, so the palette would have to be chosen on the
    reader's behalf, leaving the mark dim on half the devices.
    """
    colors = _strata_colors()
    size = 24.0
    marks = cells(size, compact=True)
    width = (size / COMPACT_ROWS) * len(COMPACT_STRATA)

    light = "".join(
        f'.s{stratum}{{fill:{colors["light"][stratum]}}}' for stratum in COMPACT_STRATA
    )
    dark = "".join(
        f'.s{stratum}{{fill:{colors["dark"][stratum]}}}' for stratum in COMPACT_STRATA
    )
    rects = "".join(
        f'<rect x="{x:.3f}" y="{y:.3f}" width="{side:.3f}" height="{side:.3f}" '
        f'class="s{stratum}"/>'
        for x, y, side, stratum in marks
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.3f} {size:.0f}" '
        f'role="img" aria-label="RAG World">'
        f"<style>{light}@media(prefers-color-scheme:dark){{{dark}}}</style>"
        f"{rects}</svg>\n"
    )


# ─── The raster ──────────────────────────────────────────────────────────────
#
# A twenty-line encoder instead of a dependency on a renderer: the mark is a set
# of rectangles with solid fills, and all it takes is a pixel buffer and `zlib`
# from the standard library.

def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _png(width: int, height: int, pixels: bytearray) -> bytes:
    raw = bytearray()
    for row in range(height):
        raw.append(0)
        start = row * width * 3
        raw += pixels[start:start + width * 3]

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def _canvas(width: int, height: int, background: str) -> bytearray:
    r, g, b = _rgb(background)
    return bytearray(bytes((r, g, b)) * width * height)


def _fill(pixels: bytearray, canvas_w: int, x: float, y: float,
          w: float, h: float, color: str) -> None:
    r, g, b = _rgb(color)
    for row in range(int(round(y)), int(round(y + h))):
        start = (row * canvas_w + int(round(x))) * 3
        pixels[start:start + int(round(w)) * 3] = bytes((r, g, b)) * int(round(w))


def render_raster(
    width: int, height: int, mark: float, mode: str, *, band: bool = False
) -> bytes:
    """The mark on a ground: the device icon and the link preview image.

    The preview image carries a band of strata along its lower edge. Without it
    the mark hung in the middle of an empty field and read as unfinished: the
    platform shows a title and a description beside it, while the image itself
    said nothing. The band holds the composition together and repeats the same
    seven strata as the mark.
    """
    colors = _strata_colors()[mode]
    pixels = _canvas(width, height, _backgrounds()[mode])

    thickness = max(4.0, height * 0.018) if band else 0.0
    marks = cells(mark, compact=False)
    mark_w = (mark / ROWS) * len(STRATA)
    left = (width - mark_w) / 2
    # The mark is centred on the field above the band rather than on the whole
    # card: otherwise it drifts down by exactly the height of the band and the
    # composition reads as accidental.
    top = (height - thickness - mark) / 2
    for x, y, side, stratum in marks:
        _fill(pixels, width, left + x, top + y, side, side, colors[stratum])

    if band:
        segment = width / len(STRATA)
        for i, stratum in enumerate(STRATA):
            _fill(pixels, width, i * segment, height - thickness,
                  segment, thickness, colors[stratum])
    return _png(width, height, pixels)


TARGETS = (
    ("favicon.svg", None),
    ("apple-touch-icon.png", (180, 180, 96.0, False)),
    ("og-image.png", (1200, 630, 404.0, True)),
)


def build(*, check: bool = False) -> list[str]:
    """Build the icons; with `check`, only name what has drifted."""
    changed: list[str] = []
    for name, raster in TARGETS:
        if raster is None:
            payload: bytes = render_favicon().encode("utf-8")
        else:
            width, height, mark, band = raster
            payload = render_raster(width, height, mark, "dark", band=band)
        target = PUBLIC / name
        current = target.read_bytes() if target.exists() else None
        if current != payload:
            changed.append(name)
            if not check:
                target.write_bytes(payload)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="write nothing, only name what has drifted")
    args = parser.parse_args()

    changed = build(check=args.check)
    if args.check:
        if changed:
            print("the icons have drifted from the mark: " + ", ".join(changed))
            return 1
        print("the icons match the mark")
        return 0
    print("the icons are built" if changed else "the icons were already built")
    for name in changed:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
