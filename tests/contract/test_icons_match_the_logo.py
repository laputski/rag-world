"""The icons match the mark drawn in the interface.

The mark lives as code in `Logo.tsx` while the icons are needed as files: a
browser tab, a home screen and a link preview are drawn by platforms that run no
code. Hence two descriptions of one drawing and the usual consequence — they
diverge, and diverge in silence.

The failure is especially unpleasant because it is invisible from the portal: the
portal shows the new drawing while the tab icon and the preview image keep the
old one, and it surfaces on somebody else's page where a link was posted.

The check demands that the icons on disk match what follows from the current
sources, and that the markup points at them.
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
    """An icon built from an old drawing lives on other people's pages."""
    stale = build_icons.build(check=True)
    assert not stale, (
        f"the icons were not built from the current mark: {stale}. "
        "Run `make icons` and commit the result."
    )


def test_every_icon_exists():
    missing = [name for name, _ in build_icons.TARGETS if not (PUBLIC / name).exists()]
    assert not missing, f"the icons are not built: {missing}"


def test_pattern_is_read_from_the_component_not_copied():
    """The pattern comes from `Logo.tsx` rather than being copied into the builder."""
    source = (ROOT / "scripts" / "build_icons.py").read_text(encoding="utf-8")
    assert "Logo.tsx" in source
    pattern = build_icons._pattern()
    assert sorted(pattern) == list("ABCDEFG")
    assert all(len(rows) == build_icons.ROWS for rows in pattern.values())
    # An empty pattern would parse without error and give empty icons.
    assert any(any(rows) for rows in pattern.values()), "the pattern of the mark is empty"


def test_colours_are_read_from_the_theme_not_copied():
    source = (ROOT / "scripts" / "build_icons.py").read_text(encoding="utf-8")
    assert "theme.ts" in source
    colors = build_icons._strata_colors()
    assert sorted(colors) == ["dark", "light"]
    for mode, palette in colors.items():
        assert sorted(palette) == list("ABCDEFG"), f"the {mode} theme is incomplete"
        for stratum, value in palette.items():
            assert re.fullmatch(r"#[0-9A-Fa-f]{6}", value), f"{mode}.{stratum}: {value}"
    assert colors["light"] != colors["dark"], (
        "the theme palettes coincide; the tab icon has stopped telling them apart"
    )


def test_favicon_carries_both_palettes():
    """One file for both themes: otherwise the mark goes dim on half the devices."""
    svg = (PUBLIC / "favicon.svg").read_text(encoding="utf-8")
    colors = build_icons._strata_colors()
    assert "prefers-color-scheme:dark" in svg
    for stratum in build_icons.COMPACT_STRATA:
        assert colors["light"][stratum] in svg, f"the light colour of stratum {stratum} is missing"
        assert colors["dark"][stratum] in svg, f"the dark colour of stratum {stratum} is missing"
    assert "<rect" in svg


def test_raster_icons_have_the_declared_size():
    """A platform crops an image of the wrong size and shows a fragment."""
    for name, raster in build_icons.TARGETS:
        if raster is None:
            continue
        width, height = raster[0], raster[1]
        data = (PUBLIC / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{name}: this is not a PNG"
        actual = struct.unpack(">II", data[16:24])
        assert actual == (width, height), f"{name}: {actual}, expected {(width, height)}"


def test_markup_points_at_the_icons():
    """An icon that is built and never referenced is seen by nobody."""
    html = INDEX.read_text(encoding="utf-8")
    for fragment in (
        'rel="icon" href="/favicon.svg"',
        'rel="apple-touch-icon" href="/apple-touch-icon.png"',
        'property="og:image" content="https://ragworld.org/og-image.png"',
        'property="og:image:width" content="1200"',
        'property="og:image:height" content="630"',
    ):
        assert fragment in html, f"the markup does not contain {fragment}"
    # The preview image is wide, and the card type has to match it: with `summary`
    # a platform crops it to a square.
    assert 'name="twitter:card" content="summary_large_image"' in html
