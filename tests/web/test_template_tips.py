"""An explanation must be reachable on a touch screen.

Native `title` never appears on a phone, and the app is opened from one every
day, so `data-tip` is the only tooltip mechanism left. The head's `<title>` is
the page title, not a tooltip, and is the one exception.

The placement guard is the trap the migration paid for: `rows.js` navigates from
anywhere on a `.row-hover[data-href]` row and is registered before the tooltip
handler, so a tip on a plain element inside such a row can never be read.
"""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATES = Path(__file__).parents[2] / "budget_forecaster" / "web" / "templates"

# The <head> of the two templates that own one.
HEAD_TITLE = {"base.html", "login.html"}

_TITLE_ATTR = re.compile(r"\btitle\s*=")
_TITLE_ELEMENT = re.compile(r"<title[\s>]")
# Tags are written over several lines, so the element name and the attribute are
# matched across them.
_TIPPED = re.compile(r"<([a-zA-Z]+)(?:\s[^<>]*)?\sdata-tip=", re.DOTALL)
# A control is skipped by the row's click handler and is what a keyboard reaches.
_TIP_BEARERS = {"button", "th", "td"}


def _templates() -> list[Path]:
    return sorted(TEMPLATES.rglob("*.html"))


def _hits(pattern: re.Pattern[str], skip_head: bool) -> list[str]:
    hits = []
    for path in _templates():
        if skip_head and path.name in HEAD_TITLE:
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if pattern.search(line):
                hits.append(f"{path.relative_to(TEMPLATES)}:{number}: {line.strip()}")
    return hits


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
    """A tip on a plain element inside a clickable row can never be read."""
    offenders = []
    for path in _templates():
        for match in _TIPPED.finditer(path.read_text()):
            if match.group(1).lower() not in _TIP_BEARERS:
                offenders.append(f"{path.relative_to(TEMPLATES)}: <{match.group(1)}>")
    assert not offenders, (
        "a tip on a plain element inside a clickable row loses the click to "
        "rows.js; put it on a button:\n" + "\n".join(offenders)
    )
