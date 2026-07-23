"""Each read-only section renders and matches the ApplicationService data."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from budget_forecaster.web.formatting import format_eur
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
        response = client.get(f"/mois/{month:%Y-%m}")
        assert response.status_code == 200
        assert str(month.year) in response.text

    def test_month_redirects_bad_segment(self, client: TestClient) -> None:
        """An unparseable month segment redirects back to /mois."""
        response = client.get("/mois/not-a-month", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/mois"

    def test_operations_lists_every_operation(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """The ledger renders one row per operation the service returns."""
        total = len(app.state.app_service.get_operations())
        html = client.get("/operations").text
        assert html.count('<td class="date">') == total

    def test_operations_uncategorized_filter(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """The uncategorized filter narrows the ledger to uncategorized rows."""
        uncategorized = len(app.state.app_service.get_uncategorized_operations())
        html = client.get("/operations?uncategorized=true").text
        assert html.count('<td class="date">') == uncategorized

    def test_operations_htmx_returns_only_rows(self, client: TestClient) -> None:
        """An HX-Request returns the rows fragment, not the full page."""
        response = client.get("/operations", headers={"HX-Request": "true"})
        body = response.text.strip()
        assert "<html" not in body
        assert body.startswith("<tr")

    def test_trends_renders(self, client: TestClient) -> None:
        """Trends shows the balance evolution and expense breakdown."""
        html = client.get("/tendances").text
        assert "Tendances" in html
        assert "Expense breakdown" in html or "dépense" in html.lower()

    def test_settings_shows_inbox_path(self, client: TestClient, app: FastAPI) -> None:
        """Settings shows the configured import inbox path."""
        inbox = str(app.state.app_service.inbox_path)
        html = client.get("/reglages").text
        assert "Réglages" in html
        assert inbox in html
