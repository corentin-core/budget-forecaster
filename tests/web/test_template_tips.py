"""An explanation must be reachable on a touch screen.

Native `title` never appears on a phone, and the app is opened from one every
day, so `data-tip` is the only tooltip mechanism left. The head's `<title>` is
the page title, not a tooltip, and is the one exception.

The placement guard is the trap the migration paid for: `rows.js` navigates from
anywhere on a `.row-hover` row and is registered before the tooltip handler, so
a tip on anything that row's handler does not skip can never be read. `<td>` and
`<th>` are not in that skip list, which is why a tip on one is only allowed
outside a clickable row.
"""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATES = Path(__file__).parents[2] / "budget_forecaster" / "web" / "templates"

# The <head> of the two templates that own one.
HEAD_TITLE = {"base.html", "login.html"}

_TITLE_ATTR = re.compile(r"\btitle\s*=")
_TITLE_ELEMENT = re.compile(r"<title[\s>]")
# Tags are written over several lines, so a tag's name and its attributes are
# matched across them: `[^<>]` spans newlines whatever the DOTALL flag says.
_TIPPED = re.compile(r"<([a-zA-Z]+)(?:\s[^<>]*)?\sdata-tip=")
_ROW = re.compile(r"<tr(?:\s[^<>]*)?>")
# Skipped by the row's click handler, and what a keyboard reaches.
_ALWAYS = {"button"}
# Safe only outside a row that is itself a click target.
_OUTSIDE_A_CLICKABLE_ROW = {"th", "td"}


def _templates() -> list[Path]:
    return sorted(TEMPLATES.rglob("*.html"))


def _hits(pattern: re.Pattern[str], skip_head: bool) -> list[str]:
    """Every match, as `path:line: source`. Scanned whole so a tag split over
    several lines cannot slip through."""
    hits = []
    for path in _templates():
        if skip_head and path.name in HEAD_TITLE:
            continue
        text = path.read_text()
        for match in pattern.finditer(text):
            number = text.count("\n", 0, match.start()) + 1
            line = text.splitlines()[number - 1].strip()
            hits.append(f"{path.relative_to(TEMPLATES)}:{number}: {line}")
    return hits


def _in_clickable_row(text: str, offset: int) -> bool:
    """Whether the nearest enclosing `<tr>` is a click target of its own."""
    rows = [m for m in _ROW.finditer(text) if m.start() < offset]
    return bool(rows) and "row-hover" in rows[-1].group(0)


def test_no_title_attribute() -> None:
    """A native tooltip is invisible on the device the app is opened from."""
    offenders = _hits(_TITLE_ATTR, skip_head=False)
    assert not offenders, "use data-tip, or make the text visible:\n" + "\n".join(
        offenders
    )


def test_no_native_title_element_outside_the_head() -> None:
    """An SVG <title> is the same tooltip, written as an element."""
    offenders = _hits(_TITLE_ELEMENT, skip_head=True)
    assert not offenders, "an SVG <title> is a desktop-only tooltip:\n" + "\n".join(
        offenders
    )


def test_a_tip_only_sits_on_something_a_row_click_skips() -> None:
    """A tip the row's own click handler would swallow can never be read."""
    offenders = []
    for path in _templates():
        text = path.read_text()
        for match in _TIPPED.finditer(text):
            if (tag := match.group(1).lower()) in _ALWAYS:
                continue
            if tag in _OUTSIDE_A_CLICKABLE_ROW and not _in_clickable_row(
                text, match.start()
            ):
                continue
            number = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{path.relative_to(TEMPLATES)}:{number}: <{tag}>")
    assert not offenders, (
        "the row's click handler does not skip this element, so the bubble never "
        "shows; put the tip on a button:\n" + "\n".join(offenders)
    )
