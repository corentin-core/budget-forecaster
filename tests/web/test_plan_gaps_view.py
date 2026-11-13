"""Tests for the "Gaps to plan" card, its full list and the ledger filter it uses."""

from datetime import date
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from budget_forecaster.core.types import BudgetColumn
from budget_forecaster.infrastructure.bootstrap import open_repository
from budget_forecaster.infrastructure.config import Config
from budget_forecaster.services.account.account_analyzer import AccountAnalyzer
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.web.app import _build_app_service
from budget_forecaster.web.plan_gaps_view import (
    CARD_ROWS,
    DEFAULT_GAP_MONTHS,
    _useful_periods,
    gap_cause,
    gap_period,
)


def _service(config_path: Path) -> ApplicationService:
    """The demo database's service, built on the test's own thread."""
    config = Config()
    config.parse(config_path)
    return _build_app_service(config, open_repository(config))


class TestMatchesTheMonthView:
    """The causes add up to what the month view says."""

    def test_each_month_adds_up(self, config_path: Path) -> None:
        """Actual minus planned of every month equals the sum of its items."""
        app = _service(config_path)
        gaps = app.get_plan_gaps(12)
        assert gaps.months, "the demo database has months that are over"

        last_day = (pd.Timestamp(gaps.months[-1]) + pd.offsets.MonthEnd(0)).date()
        report = AccountAnalyzer(
            app._persistent_account.account,  # pylint: disable=protected-access
            app.load_forecast(),
            app.get_all_links(),
        ).compute_budget_forecast(gaps.months[0], last_day)
        for month, total in zip(gaps.months, gaps.month_totals()):
            column = pd.Timestamp(month)
            expected = (
                report.loc["Total", (column, BudgetColumn.ACTUAL)]
                - report.loc["Total", (column, BudgetColumn.TOTAL_PLANNED)]
            )
            # The report rounds every category to the euro.
            assert abs(total - expected) <= len(report.index), month

    def test_window_skips_the_current_month(self, config_path: Path) -> None:
        """Only months before the balance date's month are compared."""
        app = _service(config_path)
        current = app.balance_date.replace(day=1)

        assert all(month < current for month in app.get_plan_gaps(6).months)


class TestCard:
    """The card on the trends page and its full list."""

    def test_card_on_trends(self, client: TestClient) -> None:
        """The card lists its items, each opening an existing page."""
        html = client.get("/trends").text
        card = html[html.index('id="gaps"') : html.index('id="breakdown"')]

        assert "Écarts au prévu" in card
        assert card.count('class="gaps-row"') <= CARD_ROWS
        assert 'href="/targets/' in card or 'href="/operations?' in card
        assert 'href="/month/' in card

    def test_full_list(self, client: TestClient) -> None:
        """The full list has every item and no "see all" link."""
        html = client.get("/trends/gaps?months=12").text

        assert html.count('class="gaps-row"') >= 1
        assert "gaps-more" not in html

    def test_card_swap_keeps_the_full_list(self, client: TestClient) -> None:
        """Switching the period from the full list keeps every item."""
        html = client.get("/trends/gaps/card?months=3&full=1").text

        full = client.get("/trends/gaps?months=3").text
        assert html.count('class="gaps-row"') == full.count('class="gaps-row"')
        assert "gaps-more" not in html

    def test_chip_filters_the_list_on_its_cause(self, client: TestClient) -> None:
        """A picked chip keeps only its cause and offers to show every cause again."""
        html = client.get("/trends/gaps/card?months=6&cause=budget").text

        causes = [
            line.strip() for line in html.splitlines() if 'class="gaps-cause"' in line
        ]
        assert causes
        assert all("budget" in line for line in causes)
        assert 'aria-pressed="true"' in html
        # The picked chip asks for every cause back.
        assert '&cause="' in html
        assert gap_cause("budget") is not None
        assert gap_cause("nonsense") is None

    def test_only_periods_that_change_the_window(self) -> None:
        """A period longer than the history adds nothing to the switch."""
        assert _useful_periods(2) == (3,)
        assert _useful_periods(6) == (3, 6)
        assert _useful_periods(7) == (3, 6, 12)
        assert _useful_periods(40) == (3, 6, 12)

    def test_period_falls_back_to_the_default(self) -> None:
        """A month count the switch does not offer gives the default."""
        assert gap_period("5") == DEFAULT_GAP_MONTHS
        assert gap_period("abc") == DEFAULT_GAP_MONTHS
        assert gap_period("12") == 12


class TestUnlinkedFilter:
    """The ledger filter the unplanned rows open."""

    def test_unlinked_only(self, client: TestClient) -> None:
        """No row of the filtered ledger carries a link."""
        html = client.get("/operations?unlinked=true").text
        ledger = html[html.index('id="ledger-area"') :]

        assert 'class="link-tag"' not in ledger
        assert 'name="unlinked" value="true"\n             checked' in html

    def test_filter_survives_show_more(self, client: TestClient) -> None:
        """The filter stays in the query the ledger builds its links with."""
        html = client.get(
            f"/operations?unlinked=true&date_from={date(2000, 1, 1)}"
        ).text

        assert "unlinked=true" in html
