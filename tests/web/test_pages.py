"""Each read-only section renders and matches the ApplicationService data."""

import re
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from budget_forecaster.services.application_service import (
    ApplicationService,
    UpcomingIteration,
)
from budget_forecaster.web.formatting import format_eur
from budget_forecaster.web.routes.home import _PAGE_SIZE as _UPCOMING_PAGE_SIZE
from budget_forecaster.web.routes.operations import _PAGE_SIZE
from budget_forecaster.web.viewmodels import month_to_date


class TestPages:
    """Every section renders and reflects the same data the service returns."""

    def test_home_shows_the_service_balance(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Home shows the balance the service reports, formatted."""
        service = app.state.app_service
        html = client.get("/").text
        assert "Accueil" in html
        assert format_eur(service.balance, service.currency) in html

    def test_month_renders_a_month_with_data(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A month present in the summaries renders with its year label."""
        summaries = app.state.app_service.get_monthly_summary()
        assert summaries, "demo database should yield monthly summaries"
        month = month_to_date(summaries[-1]["month"])
        response = client.get(f"/month/{month:%Y-%m}")
        assert response.status_code == 200
        assert str(month.year) in response.text

    def test_month_redirects_bad_segment(self, client: TestClient) -> None:
        """An unparseable month segment redirects back to /month."""
        response = client.get("/month/not-a-month", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/month"

    def test_operations_first_page_and_count(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """The first page shows at most one page of rows and the true total."""
        total = len(app.state.app_service.get_operations())
        html = client.get("/operations").text
        assert html.count('id="op-row-') == min(total, _PAGE_SIZE)
        assert "ledger-count" in html
        assert str(total) in html

    def test_operations_uncategorized_filter(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """The uncategorized filter narrows the ledger to uncategorized rows."""
        uncategorized = len(app.state.app_service.get_uncategorized_operations())
        html = client.get("/operations?uncategorized=true").text
        assert html.count('id="op-row-') == min(uncategorized, _PAGE_SIZE)

    def test_operations_filter_returns_area_fragment(self, client: TestClient) -> None:
        """A filter HX-Request returns the ledger area fragment, not the layout."""
        body = client.get("/operations", headers={"HX-Request": "true"}).text
        assert "<html" not in body
        assert '<table class="ledger"' in body

    def test_operations_show_more_returns_rows(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A paginated HX-Request returns row markup only, no table wrapper."""
        total = len(app.state.app_service.get_operations())
        assert total > _PAGE_SIZE, "demo database should exceed one page"
        body = client.get(
            f"/operations?offset={_PAGE_SIZE}", headers={"HX-Request": "true"}
        ).text.strip()
        assert "<table" not in body
        assert body.startswith("<tr")

    def test_trends_htmx_swaps_breakdown_only(self, client: TestClient) -> None:
        """A period switch returns only the breakdown card, not the full page."""
        body = client.get("/trends?months=6", headers={"HX-Request": "true"}).text
        assert "<html" not in body
        assert 'id="breakdown"' in body
        assert "balance-chart" not in body  # balance chart is left untouched
        assert 'class="active">6m' in body  # the requested period is active

    def test_upcoming_page_respects_size(self, client: TestClient) -> None:
        """A page of upcoming items never exceeds the page size."""
        body = client.get("/upcoming?offset=0", headers={"HX-Request": "true"}).text
        assert "<html" not in body
        assert body.count("up-date") <= _UPCOMING_PAGE_SIZE

    def test_upcoming_past_end_has_no_more_button(self, client: TestClient) -> None:
        """Requesting past the last page returns the empty OOB sentinel, no button."""
        body = client.get(
            "/upcoming?offset=100000", headers={"HX-Request": "true"}
        ).text
        assert 'id="upcoming-more"' in body
        assert "hx-get" not in body

    def test_trends_renders(self, client: TestClient) -> None:
        """Trends shows the balance evolution and expense breakdown."""
        html = client.get("/trends").text
        assert "Tendances" in html
        assert "Expense breakdown" in html or "dépense" in html.lower()

    def test_settings_shows_inbox_path(self, client: TestClient, app: FastAPI) -> None:
        """Settings shows the configured import inbox path."""
        inbox = str(app.state.app_service.inbox_path)
        html = client.get("/settings").text
        assert "Réglages" in html
        assert inbox in html


class TestUpcomingRendering:
    """The upcoming fragment lists what is still ahead."""

    def _render(self, app: FastAPI, *iterations: UpcomingIteration) -> str:
        template = app.state.templates.get_template("fragments/upcoming_items.html")
        return template.render(upcoming=list(iterations), currency="EUR")

    def test_postponed_iteration_shows_its_original_date(self, app: FastAPI) -> None:
        """A postponed iteration carries where it came from."""
        postponed = UpcomingIteration(
            planned_operation_id=7,
            iteration_date=date(2025, 4, 2),
            description="Rent",
            amount=-850.0,
            currency="EUR",
            period=None,
            postponed_from=date(2025, 3, 5),
        )
        html = self._render(app, postponed)
        assert "up-note" in html
        assert "05/03/2025" in html

    def test_plain_iteration_has_no_note(self, app: FastAPI) -> None:
        """An iteration due on its own date shows no annotation."""
        plain = UpcomingIteration(
            planned_operation_id=7,
            iteration_date=date(2025, 4, 2),
            description="Rent",
            amount=-850.0,
            currency="EUR",
            period=None,
        )
        html = self._render(app, plain)
        assert "up-note" not in html

    def test_the_description_opens_the_planned_operation(self, app: FastAPI) -> None:
        """The list names planned operations, so it leads to them."""
        item = UpcomingIteration(
            planned_operation_id=7,
            iteration_date=date(2025, 4, 2),
            description="Rent",
            amount=-850.0,
            currency="EUR",
            period=None,
        )
        html = self._render(app, item)
        assert '<a href="/targets/planned/7?return_to=/">Rent</a>' in html

    def test_an_unsaved_operation_stays_plain_text(self, app: FastAPI) -> None:
        """Without an id there is no page to open."""
        item = UpcomingIteration(
            planned_operation_id=None,
            iteration_date=date(2025, 4, 2),
            description="Rent",
            amount=-850.0,
            currency="EUR",
            period=None,
        )
        html = self._render(app, item)
        assert "/targets/planned/" not in html
        assert "Rent" in html


class TestReachingTheNamedTarget:
    """Wherever a row names its link target, the target opens from it.

    Everything goes through the routes: the app's SQLite connection belongs to
    the serving thread.
    """

    def _linked_row(self, client: TestClient, query: str = "") -> str:
        """The ledger row of an operation that names its target."""
        html = client.get(f"/operations?{query}").text
        row = next(
            (
                block[: block.find("</tr>")]
                for block in html.split('<tr id="op-row-')[1:]
                if "link-tag" in block[: block.find("</tr>")]
            ),
            "",
        )
        assert row, "the demo ledger should list a linked operation"
        return row

    def _target_href(self, markup: str) -> str:
        """The target URL the tag points at."""
        found = re.search(r'class="link-tag" href="(/targets/[^"?]+)', markup)
        assert found, "the tag should be a link to its target"
        return found.group(1)

    def test_the_ledger_tag_opens_the_target_and_comes_back(
        self, client: TestClient
    ) -> None:
        """One click out, one click back to the same filtered ledger."""
        row = self._linked_row(client, "category=RENT")
        found = re.search(r'class="link-tag" href="([^"]+)"', row)
        assert found, "the tag should be a link to its target"
        page = client.get(found.group(1).replace("&amp;", "&"))
        assert page.status_code == 200
        assert 'href="/operations?category=RENT"' in page.text

    def test_every_link_in_the_row_keeps_the_filters(self, client: TestClient) -> None:
        """A row's links all lead back where the row was read."""
        row = self._linked_row(client, "category=RENT")
        assert row.count("return_to=/operations%3Fcategory%3DRENT") == 3

    def test_the_operation_detail_opens_the_target(self, client: TestClient) -> None:
        """The phone layout hides the ledger's link icon, so the detail page carries it."""
        row = self._linked_row(client)
        found = re.search(r'<a href="(/operations/\d+)\?', row)
        assert found, "the row should link to the operation"
        html = client.get(found.group(1)).text
        assert re.search(r'<dd>\s*<a href="/targets/', html)

    def test_two_hops_out_come_back_two_hops_in(self, client: TestClient) -> None:
        """Ledger to operation to target, then back down the same nested path."""
        row = self._linked_row(client, "category=RENT")
        to_operation = re.search(r'<a href="(/operations/\d+\?return_to=[^"]+)"', row)
        assert to_operation, "the row should link to the operation"
        operation_url = to_operation.group(1)

        detail = client.get(operation_url).text
        to_target = re.search(r'<dd>\s*<a href="([^"]+)"', detail)
        assert to_target, "the detail page should link to the target"

        target = client.get(to_target.group(1).replace("&amp;", "&"))
        assert target.status_code == 200
        back_to_operation = re.search(r'class="btn" href="([^"]+)"', target.text)
        assert back_to_operation, "the target page should offer a way back"
        assert back_to_operation.group(1).startswith(operation_url.split("?")[0])

        again = client.get(back_to_operation.group(1))
        assert again.status_code == 200
        assert '<p class="back"><a href="/operations?category=RENT">' in again.text

    def test_the_month_drilldown_opens_the_target(self, client: TestClient) -> None:
        """The drill-down keeps its row click while the tag gets its own target."""
        month = client.get("/month").text
        fragments = re.findall(r'data-url="(/month/[^"]+)"', month)
        assert fragments, "the month view should offer drill-downs"
        tagged = next(
            (
                html
                for html in (client.get(url).text for url in fragments)
                if "link-tag" in html
            ),
            "",
        )
        assert tagged, "a drill-down should show an attributed linked operation"
        assert 'class="attributed-row" data-href="/operations/' in tagged
        assert client.get(self._target_href(tagged)).status_code == 200


def _categorize_everything(client: TestClient) -> None:
    """Leave nothing for Home's categorize tile to count."""
    page = client.get("/operations?uncategorized=true").text
    pending = re.findall(r'name="ids" value="(\d+)"', page)
    assert pending, "the demo database should have uncategorized operations"
    response = client.post(
        "/operations/categorize",
        data={"ids": pending, "bulk_category": "groceries"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert not re.findall(
        r'name="ids" value="(\d+)"', client.get("/operations?uncategorized=true").text
    )


class TestHomeKeepsItsShape:
    """Home fills every slot on every visit, so nothing moves between them."""

    @staticmethod
    def _slots(html: str) -> list[str]:
        """Which slots the page holds, in order, ignoring their state."""
        names = {
            'class="tile': "tile",
            'id="overdue-card"': "overdue",
            'class="card"': "card",
        }
        found = re.findall(r'class="tile\b|id="overdue-card"|class="card"', html)
        return [names[match] for match in found]

    def test_the_categorize_slot_stays_when_there_is_nothing_to_do(
        self, client: TestClient
    ) -> None:
        """Zero reads as a settled count, not as a missing tile."""
        _categorize_everything(client)

        html = client.get("/").text

        assert len(self._slots(html)) == len(self._slots(client.get("/").text))
        # The band's own end tag is not the first one: the hero is a section too.
        band = html[html.find('class="summary"') : html.find('id="overdue-card"')]
        assert band.count('class="tile') == 3
        assert "Rien à classer" in band
        assert "uncategorized=true" not in band

    def test_the_slots_are_the_same_busy_or_quiet(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The page keeps its structure whether or not anything needs attention."""
        busy = self._slots(client.get("/").text)

        _categorize_everything(client)
        monkeypatch.setattr(
            ApplicationService, "get_overdue_iterations", lambda self: ()
        )

        quiet = client.get("/").text
        assert "Rien à classer" in quiet
        assert "overdue-item" not in quiet
        assert self._slots(quiet) == busy
