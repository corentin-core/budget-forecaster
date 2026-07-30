"""Sizes, colours and shadows in the stylesheet must come from :root tokens.

Without this, each use site writes its own literal: that is how the file reached
eighteen font sizes and five near-identical paddings.

Not guarded yet, because each needs its own token first: `border` (a hairline
width), `width` / `height`, and `font-weight`.
"""

from __future__ import annotations

import re
from pathlib import Path

STYLESHEET = (
    Path(__file__).parents[2] / "budget_forecaster" / "web" / "static" / "app.css"
)

GUARDED = re.compile(
    r"^(font-size|line-height|border-radius|box-shadow|min-height|color"
    r"|background|background-color|outline|outline-offset"
    r"|padding(-top|-right|-bottom|-left|-inline|-block)?"
    r"|margin(-top|-right|-bottom|-left|-inline|-block)?"
    r"|(row-|column-)?gap)$"
)

KEYWORDS = {
    "auto",
    "inherit",
    "initial",
    "unset",
    "none",
    "transparent",
    "currentColor",
}

# Unitless line heights and zero carry no design decision.
FREE = re.compile(r"^(0|1|[0-9]*\.[0-9]+)$")

_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(")

# selector -> why this one stays literal. Keys are the selector as written, with
# whitespace collapsed. Anything absent must use a token, so an entry here is a
# deliberate exception — and `test_exemptions_are_needed` fails once it is not.
EXEMPT: dict[str, str] = {
    ".bottombar .badge": "nudge off the centre line, not spacing",
    ".chart-dot": "negative half of its own width",
    ".sr-only": "the visually-hidden clip trick",
    ".donut-total": "SVG user units in a viewBox, not a font size",
    ".login-body": "a full-viewport login screen",
}

_VAR = re.compile(r"var\(\s*(--[\w-]+)\s*\)")
_ENV = re.compile(r"env\([^()]*\)")
_CALL = re.compile(r"[\w-]*\(")


def _rules() -> list[tuple[str, str]]:
    """Every (selector, declaration block) pair, comments stripped."""
    css = re.sub(r"/\*.*?\*/", "", STYLESHEET.read_text(), flags=re.S)
    rules: list[tuple[str, str]] = []
    pending: list[str] = []
    buffer = ""
    for char in css:
        if char == "{":
            pending.append(" ".join(buffer.split()))
            buffer = ""
        elif char == "}":
            rules.append((pending.pop() if pending else "", buffer))
            buffer = ""
        else:
            buffer += char
    return rules


def _declarations() -> list[tuple[str, str, str]]:
    """Every (selector, property, value), token definitions aside."""
    found = []
    for selector, block in _rules():
        for decl in block.split(";"):
            prop, sep, value = decl.partition(":")
            prop, value = prop.strip().lower(), value.strip()
            if sep and prop and value and not prop.startswith("--"):
                found.append((selector, prop, value))
    return found


def _strip_calls(value: str) -> str:
    """Bare the arguments so a literal cannot hide inside a function.

    `var(--x, 7px)` keeps its fallback: that is a literal wearing a token's
    clothes. `env()` names a platform inset, so it goes whole.
    """
    value = _ENV.sub(" ", _VAR.sub(" ", value))
    return _CALL.sub(" ", value).replace(")", " ").replace(",", " ")


def _is_tokenised(value: str) -> bool:
    """True when nothing left after resolving tokens is a bare literal."""
    # A percentage is a mix ratio inside color-mix(), a length anywhere else.
    ratio = "color-mix(" in value
    parts = _strip_calls(value).split()
    return all(
        part in KEYWORDS
        or FREE.match(part)
        or _is_operator(part)
        or (ratio and part.endswith("%"))
        for part in parts
    )


def _is_operator(part: str) -> bool:
    return part in {"+", "-", "*", "/", "solid", "dashed", "in", "srgb"}


def test_guarded_properties_use_tokens() -> None:
    """No guarded property carries a literal outside :root."""
    offenders = [
        f"{selector} {{ {prop}: {value} }}"
        for selector, prop, value in _declarations()
        if GUARDED.match(prop) and not _is_tokenised(value) and selector not in EXEMPT
    ]
    assert not offenders, "literal values outside :root:\n" + "\n".join(offenders)


def test_a_theme_is_one_declaration_per_token() -> None:
    """No second palette: the switcher writes color-scheme and light-dark()
    picks the side, so a duplicated dark block would ignore the switch."""
    css = STYLESHEET.read_text()
    assert "prefers-color-scheme" not in css
    assert "color-scheme: light dark" in css


def test_every_colour_token_declares_both_sides() -> None:
    """A colour literal with no light-dark() pair is one the switcher cannot
    move: it keeps its light value in the dark theme."""
    offenders = [
        decl.strip()
        for selector, block in _rules()
        if selector == ":root"
        for decl in block.split(";")
        if decl.strip().startswith("--")
        and _COLOUR.search(decl)
        and "light-dark(" not in decl
    ]
    assert not offenders, "colours with no dark side:\n" + "\n".join(offenders)


def test_exemptions_are_needed() -> None:
    """An exemption whose value would now pass on its own is stale."""
    stale = [
        selector
        for selector, prop, value in _declarations()
        if selector in EXEMPT and GUARDED.match(prop) and not _is_tokenised(value)
    ]
    assert set(EXEMPT) == set(
        stale
    ), f"stale exemptions: {sorted(set(EXEMPT) - set(stale))}"
