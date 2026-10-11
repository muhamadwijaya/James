"""
Central theme definition for the Proxmark3 Toolkit GUI.

Colors were sampled directly from the reference design so the rendered
application matches it as closely as possible. Everything here is static
styling only -- no device logic lives in this module.
"""

from __future__ import annotations


class Color:
    """Flat palette of every colour used across the UI."""

    # --- Backgrounds -----------------------------------------------------
    WINDOW = "#02090f"          # app window / behind everything
    SIDEBAR = "#040d13"         # left navigation rail
    CONTENT = "#030a10"         # scrollable content area
    HEADER = "#050e15"          # top status bar strip

    CARD = "#08141c"            # standard card surface
    CARD_ALT = "#071019"        # inner / nested panel surface
    TILE = "#0a1821"            # quick-tool tiles, log rows, combo boxes
    TILE_HOVER = "#0f2129"      # hover state for tiles / nav
    INPUT = "#0a1a22"           # text inputs / console input

    # --- Borders ---------------------------------------------------------
    BORDER = "#15303a"          # default card / panel outline
    BORDER_SOFT = "#102029"     # subtle dividers
    BORDER_GREEN = "#1d5a4f"    # greenish card outline (glow cards)
    DIVIDER = "#122029"         # vertical / horizontal separators

    # --- Greens (accent) -------------------------------------------------
    GREEN = "#2ee89c"           # primary accent
    GREEN_BRIGHT = "#35f0a4"    # hover / emphasis
    GREEN_DIM = "#22c88a"       # pressed
    GREEN_DEEP = "#0f8f63"      # darker accent / icon strokes
    GREEN_DOT = "#1ee06a"       # status "connected" indicator
    GREEN_GLOW = "#123a2f"      # faint green fill (active nav, tabs)
    GREEN_SOFT = "#0c2a22"      # very faint green fill

    # --- Text ------------------------------------------------------------
    TEXT = "#e6f1fb"            # primary headings
    TEXT_DIM = "#aec4d6"        # body / values
    TEXT_MUTED = "#6c8498"      # labels / secondary
    TEXT_FAINT = "#45586b"      # placeholders / column headers
    TEXT_CYAN = "#7fb8c6"       # subtitle accents

    # --- Console ---------------------------------------------------------
    CONSOLE_BG = "#030b11"
    CONSOLE_GREEN = "#38d68f"   # command echo
    CONSOLE_TEXT = "#c6d6e6"    # output lines
    CONSOLE_STAR = "#2ee89c"    # [*] / [+] markers
    CONSOLE_CURSOR = "#2ee89c"

    # --- Misc ------------------------------------------------------------
    SCROLL = "#16303a"
    SHADOW = "#000000"


class Font:
    """Font family names registered at runtime (see resources.load_fonts)."""

    DISPLAY = "Exo 2"           # logo / brand wordmark
    UI = "Roboto"              # general interface text
    MONO = "Roboto Mono"        # console / hex / logs


# Convenience sizing constants shared across widgets.
class Metrics:
    SIDEBAR_W = 230
    HEADER_H = 92
    RADIUS = 14
    RADIUS_SM = 10
    CARD_PAD = 22
    GAP = 18
