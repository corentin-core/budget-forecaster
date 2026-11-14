"""The icon set and the controls built on it."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEMPLATES = Path(__file__).parents[2] / "budget_forecaster" / "web" / "templates"
ICON_MACROS = TEMPLATES / "macros" / "icons.html"


def _icon_names() -> set[str]:
    return set(re.findall(r'^\s*"([a-z]+)": \'<', ICON_MACROS.read_text(), re.M))


def test_every_icon_used_is_drawn() -> None:
    """An unknown name renders an empty square instead of failing."""
    used = {
        name
        for path in TEMPLATES.rglob("*.html")
        for name in re.findall(r'icon\("([a-z]+)"\)', path.read_text())
    }
    assert used, "templates should use the icon macro"
    assert used <= _icon_names(), f"no drawing for {sorted(used - _icon_names())}"


def test_icons_come_from_the_shared_macro() -> None:
    """A second drawing of an action is how two screens end up disagreeing."""
    drawn_elsewhere = [
        str(path.relative_to(TEMPLATES))
        for path in TEMPLATES.rglob("*.html")
        if path != ICON_MACROS and 'viewBox="0 0 24 24"' in path.read_text()
    ]
    assert not drawn_elsewhere


PAGES = [
    "/",
    "/operations",
    "/operations/1",
    "/targets",
    "/targets?view=planned",
    "/targets/planned/1",
    "/targets/budget/new",
]


@pytest.mark.parametrize("url", PAGES)
def test_every_tool_shows_its_label(client: TestClient, url: str) -> None:
    """A tool is an icon over a label: an icon alone is a guess on a phone."""
    page = client.get(url).text
    tools = re.findall(
        r'class="btn tool[^"]*"[^>]*>(.*?)</(?:a|button|summary)>', page, re.S
    )
    assert tools, f"{url} should have a toolbar or a filter button"
    for tool in tools:
        assert '<svg class="icon"' in tool
        assert re.search(r"<span>\s*\S", tool), tool


class TestFilterCount:
    """The filter button counts the filters folded behind it."""

    @staticmethod
    def _count(page: str) -> str | None:
        badge = re.search(r'<span class="filter-count" (hidden)?\s*>(\d+)', page)
        assert badge, "the page should have a filter button"
        return None if badge.group(1) else badge.group(2)

    def test_ledger_without_filters_shows_no_count(self, client: TestClient) -> None:
        """A badge reading 0 would be one more thing to read for nothing."""
        assert self._count(client.get("/operations").text) is None

    def test_ledger_counts_its_active_filters(self, client: TestClient) -> None:
        """Each folded filter that narrows the list adds one."""
        page = client.get("/operations?unlinked=true&category=groceries").text
        assert self._count(page) == "2"

    def test_active_only_is_the_default(self, client: TestClient) -> None:
        """Ticked by default, "active only" counts once it is cleared."""
        assert self._count(client.get("/targets").text) is None
        assert self._count(client.get("/targets?submitted=1").text) == "1"
