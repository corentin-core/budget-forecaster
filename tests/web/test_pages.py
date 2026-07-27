"""Each read-only section renders and matches the ApplicationService data."""

from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from budget_forecaster.services.application_service import UpcomingIteration
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


class TestUpcomingLateRendering:
    """The upcoming fragment flags overdue (late) iterations."""

    def _render(self, app: FastAPI, *iterations: UpcomingIteration) -> str:
        template = app.state.templates.get_template("fragments/upcoming_items.html")
        return template.render(upcoming=list(iterations), currency="EUR")

    def test_late_iteration_is_marked(self, app: FastAPI) -> None:
        """A late iteration gets the late class and warning marker."""
        late = UpcomingIteration(
            iteration_date=date(2025, 3, 26),
            description="Salary",
            amount=2940.0,
            currency="EUR",
            period=None,
            late=True,
        )
        html = self._render(app, late)
        assert 'class="late"' in html
        assert "⚠" in html

    def test_on_time_iteration_is_not_marked(self, app: FastAPI) -> None:
        """A non-late iteration has no late class nor marker."""
        on_time = UpcomingIteration(
            iteration_date=date(2025, 3, 26),
            description="Rent",
            amount=-850.0,
            currency="EUR",
            period=None,
            late=False,
        )
        html = self._render(app, on_time)
        assert 'class="late"' not in html
        assert "⚠" not in html
