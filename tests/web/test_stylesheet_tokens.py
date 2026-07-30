"""Sizes, colours and shadows in the stylesheet must come from :root tokens.

Without this, each use site writes its own literal: that is how the file reached
eighteen font sizes and five near-identical paddings.
"""

from __future__ import annotations

import re
from pathlib import Path

STYLESHEET = (
    Path(__file__).parents[2] / "budget_forecaster" / "web" / "static" / "app.css"
)

# Properties whose value must resolve to a token.
GUARDED = re.compile(
    r"^(font-size|border-radius|box-shadow|min-height|color|background-color|outline"
    r"|padding(-top|-right|-bottom|-left)?|margin(-top|-right|-bottom|-left)?|gap)$"
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

# Values that carry no design decision, whatever the property.
FREE_VALUES = {"0", "50%", "100vh", "100%"}

# (selector, property) -> why this one stays literal. Anything not listed must
# use a token, so adding an entry here is a deliberate, reviewed exception.
EXEMPT: dict[tuple[str, str], str] = {
    (".bottombar .badge", "margin-left"): "nudge off the centre line, not spacing",
    (".chart-dot", "margin"): "negative half of its own width",
    (".sr-only", "margin"): "the visually-hidden clip trick",
    (".donut-total", "font-size"): "SVG user units in a viewBox, not a font size",
    (".donut-legend .legend-members ul", "padding"): "indent derived from swatch + gap",
}


def _declarations() -> list[tuple[str, str, str]]:
    """Every (selector, property, value) in the stylesheet, tokens themselves aside."""
    css = re.sub(r"/\*.*?\*/", "", STYLESHEET.read_text(), flags=re.S)
    found: list[tuple[str, str, str]] = []
    stack: list[str] = []
    for chunk in re.split(r"([{}])", css):
        if chunk == "{":
            continue
        if chunk == "}":
            if stack:
                stack.pop()
            continue
        head, _, decls = chunk.rpartition(";")
        body = f"{head};{decls}" if head else decls
        for decl in body.split(";"):
            prop, sep, value = decl.partition(":")
            if not sep:
                continue
            prop, value = prop.strip(), value.strip()
            if prop and value and not prop.startswith("--"):
                found.append((stack[-1] if stack else "", prop, value))
        selector = decls.strip().splitlines()[-1].strip() if decls.strip() else ""
        stack.append(selector)
    return found


_FUNCTION = re.compile(r"[a-z-]*\((?:[^()]|\([^()]*\))*\)")


def _is_tokenised(value: str) -> bool:
    """True when nothing outside a function call is a bare literal."""
    return all(
        part in KEYWORDS or part in FREE_VALUES
        for part in _FUNCTION.sub(" ", value).split()
    )


def test_guarded_properties_use_tokens() -> None:
    """No guarded property carries a literal outside :root."""
    offenders = [
        f"{selector} {{ {prop}: {value} }}"
        for selector, prop, value in _declarations()
        if GUARDED.match(prop)
        and not _is_tokenised(value)
        and (selector, prop) not in EXEMPT
    ]
    assert not offenders, "literal values outside :root:\n" + "\n".join(offenders)


def test_exemptions_still_apply() -> None:
    """An exemption matching nothing is stale."""
    live = {(selector, prop) for selector, prop, _ in _declarations()}
    assert not [key for key in EXEMPT if key not in live]
