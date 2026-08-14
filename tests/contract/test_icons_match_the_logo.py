"""Значки отвечают знаку, нарисованному в интерфейсе.

Знак живёт кодом в `Logo.tsx`, а значки нужны файлами: вкладку браузера,
домашний экран и предпросмотр ссылки рисуют площадки, которые кода портала не
выполняют. Отсюда два описания одного рисунка и обычная для такой пары беда —
они расходятся, и расходятся молча.

Отказ здесь особенно неприятен тем, что его не видно с портала. Знак в шапке
показывает новый рисунок, значок вкладки и картинка предпросмотра — старый, и
обнаруживается это на чужой странице, куда кто-то поставил ссылку.

Проверка требует, чтобы значки на диске совпадали с тем, что собирается из
нынешних исходников, и чтобы разметка на них ссылалась.
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import build_icons  # noqa: E402

PUBLIC = ROOT / "ui" / "public"
INDEX = ROOT / "ui" / "index.html"


def test_icons_on_disk_are_built_from_the_current_logo():
    """Значок, собранный из прежнего рисунка, живёт на чужих страницах."""
    stale = build_icons.build(check=True)
    assert not stale, (
        f"значки собраны не из нынешнего знака: {stale}. "
        "Выполните `make icons` и зафиксируйте результат."
    )


def test_every_icon_exists():
    missing = [name for name, _ in build_icons.TARGETS if not (PUBLIC / name).exists()]
    assert not missing, f"значки не собраны: {missing}"


def test_pattern_is_read_from_the_component_not_copied():
    """Рисунок берётся из `Logo.tsx`, а не переписан в сборщик значков."""
    source = (ROOT / "scripts" / "build_icons.py").read_text(encoding="utf-8")
    assert "Logo.tsx" in source
    pattern = build_icons._pattern()
    assert sorted(pattern) == list("ABCDEFG")
    assert all(len(rows) == build_icons.ROWS for rows in pattern.values())
    # Пустой рисунок разобрался бы без ошибки и дал бы пустые значки.
    assert any(any(rows) for rows in pattern.values()), "рисунок знака пуст"


def test_colours_are_read_from_the_theme_not_copied():
    source = (ROOT / "scripts" / "build_icons.py").read_text(encoding="utf-8")
    assert "theme.ts" in source
    colors = build_icons._strata_colors()
    assert sorted(colors) == ["dark", "light"]
    for mode, palette in colors.items():
        assert sorted(palette) == list("ABCDEFG"), f"тема {mode} неполна"
        for stratum, value in palette.items():
            assert re.fullmatch(r"#[0-9A-Fa-f]{6}", value), f"{mode}.{stratum}: {value}"
    assert colors["light"] != colors["dark"], (
        "палитры тем совпали; значок вкладки перестал различать тему"
    )


def test_favicon_carries_both_palettes():
    """Один файл на обе темы: иначе знак тускнеет на половине устройств."""
    svg = (PUBLIC / "favicon.svg").read_text(encoding="utf-8")
    colors = build_icons._strata_colors()
    assert "prefers-color-scheme:dark" in svg
    for stratum in build_icons.COMPACT_STRATA:
        assert colors["light"][stratum] in svg, f"нет светлого цвета страты {stratum}"
        assert colors["dark"][stratum] in svg, f"нет тёмного цвета страты {stratum}"
    assert "<rect" in svg


def test_raster_icons_have_the_declared_size():
    """Площадка обрезает картинку не того размера и показывает обрубок."""
    for name, raster in build_icons.TARGETS:
        if raster is None:
            continue
        width, height = raster[0], raster[1]
        data = (PUBLIC / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{name}: это не PNG"
        actual = struct.unpack(">II", data[16:24])
        assert actual == (width, height), f"{name}: {actual}, ожидалось {(width, height)}"


def test_markup_points_at_the_icons():
    """Собранный значок, на который не ссылаются, никто не увидит."""
    html = INDEX.read_text(encoding="utf-8")
    for fragment in (
        'rel="icon" href="/favicon.svg"',
        'rel="apple-touch-icon" href="/apple-touch-icon.png"',
        'property="og:image" content="https://ragworld.org/og-image.png"',
        'property="og:image:width" content="1200"',
        'property="og:image:height" content="630"',
    ):
        assert fragment in html, f"в разметке нет {fragment}"
    # Картинка предпросмотра широкая, и род карточки обязан ей отвечать:
    # при `summary` площадка обрежет её до квадрата.
    assert 'name="twitter:card" content="summary_large_image"' in html
