"""Shared Unicode display symbols for TUI components."""

import enum


class DisplaySymbol(enum.StrEnum):
    """Unicode symbols used across the TUI for consistent display."""

    SEPARATOR = "\u2500"  # ─
    ARROW_LEFT = "\u2190"  # ←
    ARROW_RIGHT = "\u2192"  # →
    ARROW_UP = "\u2191"  # ↑
    ARROW_DOWN = "\u2193"  # ↓
    EM_DASH = "\u2014"  # —
    EURO = "\u20ac"  # €
    PLAY = "\u25ba"  # ►
    STAR = "\u2605"  # ★
