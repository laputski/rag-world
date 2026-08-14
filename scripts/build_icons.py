#!/usr/bin/env python3
"""Значки портала: файл вкладки, значок для устройств и картинка предпросмотра.

Знак нарисован кодом в `ui/src/components/Logo.tsx`, а значки нужны файлами:
вкладка браузера, значок на домашнем экране и предпросмотр ссылки читаются
площадками, которые кода портала не выполняют. Отсюда задача — получить те же
клетки в файлах, не заводя второго описания знака.

Рисунок и цвета поэтому **читаются из исходников интерфейса**, а не
переписываются сюда. Разбор узкий и проверяемый: если он не нашёл семь страт
или двадцать восемь клеток, сборка останавливается. Расхождение так становится
громким, тогда как переписанный вручную рисунок разошёлся бы молча и обнаружился
бы на чужом предпросмотре.

Растр пишется своими руками поверх `zlib`: знак состоит из прямоугольников, и
рисовать их в буфер пикселей проще, чем заводить зависимость от разрисовщика
векторной графики ради четырнадцати квадратов.

Использование::

    python3 scripts/build_icons.py
    python3 scripts/build_icons.py --check   # проверить, не собирая
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

#: Страты и строки упрощённого рисунка. Держатся согласованными с `Logo.tsx`
#: проверкой `tests/contract/test_icons_match_the_logo.py`.
COMPACT_STRATA = ["A", "C", "E", "G"]
COMPACT_ROWS = 3

#: Нейтральные цвета портала для подложек. Их немного, и берутся они там же.
NEUTRAL_RE = re.compile(
    r"(?P<mode>light|dark):\s*\{\s*bg:\s*\"(?P<bg>#[0-9A-Fa-f]{6})\""
)


def _strata_colors() -> dict[str, dict[str, str]]:
    """Цвета страт из `theme.ts`, по теме."""
    text = THEME.read_text(encoding="utf-8")
    block = re.search(
        r"STRATUM_COLORS[^=]*=\s*\{(?P<body>.*?)\n\};", text, re.S
    )
    if not block:
        raise SystemExit("в theme.ts не найдено объявление цветов страт")

    out: dict[str, dict[str, str]] = {}
    for mode in ("light", "dark"):
        section = re.search(
            rf"{mode}:\s*\{{(?P<body>.*?)\}},", block.group("body"), re.S
        )
        if not section:
            raise SystemExit(f"в theme.ts нет палитры темы {mode}")
        found = dict(re.findall(r"([A-G]):\s*\"(#[0-9A-Fa-f]{6})\"", section.group("body")))
        missing = [s for s in STRATA if s not in found]
        if missing:
            raise SystemExit(f"в палитре темы {mode} нет страт {missing}")
        out[mode] = found
    return out


def _backgrounds() -> dict[str, str]:
    text = THEME.read_text(encoding="utf-8")
    found = {m.group("mode"): m.group("bg") for m in NEUTRAL_RE.finditer(text)}
    missing = [mode for mode in ("light", "dark") if mode not in found]
    if missing:
        raise SystemExit(f"в theme.ts не найден фон тем {missing}")
    return found


def _pattern() -> dict[str, list[bool]]:
    """Рисунок знака из `Logo.tsx`."""
    text = LOGO.read_text(encoding="utf-8")
    block = re.search(r"PATTERN[^=]*=\s*\{(?P<body>.*?)\n\};", text, re.S)
    if not block:
        raise SystemExit("в Logo.tsx не найдено объявление рисунка знака")
    out: dict[str, list[bool]] = {}
    for stratum, body in re.findall(r"([A-G]):\s*\[(.*?)\]", block.group("body"), re.S):
        out[stratum] = [value.strip() == "true" for value in body.split(",")]
    missing = [s for s in STRATA if s not in out]
    if missing:
        raise SystemExit(f"в рисунке знака нет страт {missing}")
    wrong = {s: len(v) for s, v in out.items() if len(v) != ROWS}
    if wrong:
        raise SystemExit(f"в рисунке знака строк не {ROWS}: {wrong}")
    return out


def cells(size: float, compact: bool) -> list[tuple[float, float, float, str]]:
    """Клетки знака:x, y, сторона, код страты."""
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
    """Значок вкладки: один файл, меняющий палитру вместе с темой браузера.

    Растровый значок так не умеет, поэтому пришлось бы выбирать палитру за
    читателя и мириться с тем, что на половине устройств знак тускнеет.
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


# ─── Растр ───────────────────────────────────────────────────────────────────
#
# Кодировщик на двадцать строк вместо зависимости от разрисовщика: знак есть
# набор прямоугольников со сплошной заливкой, и всё, что нужно, — буфер пикселей
# и `zlib` из стандартной поставки.

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
    """Знак на подложке: значок устройства и картинка предпросмотра.

    Картинка предпросмотра несёт полосу страт по нижнему краю. Без неё знак
    висел посреди пустого поля и читался незаконченным: площадка показывает
    рядом заголовок и описание, но сама картинка не говорила ничего. Полоса
    держит композицию и повторяет ту же семёрку, что и знак.
    """
    colors = _strata_colors()[mode]
    pixels = _canvas(width, height, _backgrounds()[mode])

    thickness = max(4.0, height * 0.018) if band else 0.0
    marks = cells(mark, compact=False)
    mark_w = (mark / ROWS) * len(STRATA)
    left = (width - mark_w) / 2
    # Знак центрируется по полю над полосой, а не по всей карточке: иначе он
    # съезжает к низу ровно на толщину полосы и композиция читается случайной.
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
    """Собрать значки; при `check` только сказать, что разошлось."""
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
                        help="не записывать, только назвать разошедшееся")
    args = parser.parse_args()

    changed = build(check=args.check)
    if args.check:
        if changed:
            print("значки разошлись со знаком: " + ", ".join(changed))
            return 1
        print("значки отвечают знаку")
        return 0
    print("значки собраны" if changed else "значки уже были собраны")
    for name in changed:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
