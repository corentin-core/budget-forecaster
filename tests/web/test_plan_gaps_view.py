"""Tests for the "Gaps to plan" card, its full list and the ledger filter it uses."""

import re
from datetime import date
from html import unescape
from pathlib import Path

import pandas as pd
from dateutil.relativedelta import relativedelta
from fastapi.testclient import TestClient

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import (
    DateRange,
    RecurringDateRange,
    RecurringDay,
)
from budget_forecaster.core.types import BudgetColumn, Category
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.infrastructure.bootstrap import open_repository
from budget_forecaster.infrastructure.config import Config
from budget_forecaster.services.account.account_analyzer import AccountAnalyzer
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.forecast.plan_gaps import GapCause, GapItem, PlanGaps
from budget_forecaster.web.app import _build_app_service
from budget_forecaster.web.plan_gaps_view import (
    CARD_ROWS,
    DEFAULT_GAP_MONTHS,
    GapFix,
    _fix,
    _FixContext,
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

    def test_fix_is_confirmed_on_the_card(self, client: TestClient) -> None:
        """A fix posts its split from the card, and comes back to it."""
        card = client.get("/trends/gaps?months=12").text
        form = re.search(
            r'<form method="post" action="([^"]+/split)" class="gaps-fix".*?</form>',
            card,
            re.S,
        )
        assert form is not None
        fields = {
            name: unescape(value)
            for name, value in re.findall(
                r'name="([^"]+)" value="([^"]*)"', form.group(0)
            )
        }

        response = client.post(form.group(1), data=fields, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"].startswith("/trends/gaps?months=")

    def test_adjust_opens_the_split_filled_in(self, client: TestClient) -> None:
        """ "Adjust…" opens the same change on the edit page, to retouch it."""
        card = client.get("/trends/gaps?months=12").text
        start = card.index('class="action-link" href="') + len(
            'class="action-link" href="'
        )
        url = card[start : card.index('"', start)].replace("&amp;", "&")

        assert "data-split-section open" in client.get(url).text

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


class TestWayBack:
    """The ledger opened from the card leads back to it."""

    def test_unplanned_row_opens_the_ledger_with_a_way_back(
        self, client: TestClient
    ) -> None:
        """The ledger link of an unplanned row carries the list as its return."""
        card = client.get("/trends/gaps").text
        start = card.index('href="/operations?') + len('href="')
        url = card[start : card.index('"', start)].replace("&amp;", "&")

        ledger = client.get(url).text
        assert '<p class="back"><a href="/trends/gaps?months=' in ledger
        assert 'name="return_to" value="/trends/gaps?months=' in ledger

    def test_operation_detail_returns_to_the_same_ledger(
        self, client: TestClient
    ) -> None:
        """An operation opened from that ledger goes back to it, return included."""
        ledger = client.get("/operations?return_to=/trends%23gaps").text
        start = ledger.index('href="/operations/') + len('href="')
        detail = client.get(ledger[start : ledger.index('"', start)]).text
        start = detail.index('<p class="back"><a href="') + len(
            '<p class="back"><a href="'
        )
        back = detail[start : detail.index('"', start)].replace("&amp;", "&")

        assert '<p class="back"><a href="/trends#gaps">' in client.get(back).text

    def test_outside_return_is_dropped(self, client: TestClient) -> None:
        """Only a page of the app can be the return."""
        ledger = client.get("/operations?return_to=https://example.com").text

        assert 'class="back"' not in ledger

    def test_full_list_rows_come_back_to_it(self, client: TestClient) -> None:
        """A row of the full list returns to that list, not to the card."""
        html = client.get("/trends/gaps?months=3").text

        assert "return_to=%2Ftrends%2Fgaps%3Fmonths%3D3" in html


_MONTHS = tuple(date(2026, month, 1) for month in (7, 8, 9, 10))
_TODAY = date(2026, 11, 13)
_CONTEXT = _FixContext(
    currency="EUR",
    back="/trends#gaps",
    today=_TODAY,
    month=date(2026, 11, 1),
    window_end=date(2026, 10, 31),
)


def _groceries_budget(amount: float = -400.0) -> Budget:
    return Budget(
        record_id=1,
        description="Groceries",
        amount=Amount(amount, "EUR"),
        category=Category.GROCERIES,
        date_range=RecurringDateRange(
            DateRange(date(2026, 1, 1), relativedelta(months=1)),
            relativedelta(months=1),
        ),
    )


def _electricity(last: date | None = None) -> PlannedOperation:
    return PlannedOperation(
        record_id=2,
        description="Electricity",
        amount=Amount(-85.0, "EUR"),
        category=Category.ELECTRICITY,
        date_range=RecurringDay(date(2026, 1, 5), relativedelta(months=1), last),
    )


def _item(
    cause: GapCause,
    actual: tuple[float, ...],
    *,
    target: Budget | PlannedOperation | None = None,
    planned: tuple[float, ...] = (0.0,) * 4,
    missed: tuple[date, ...] = (),
    latest_paid: float | None = None,
) -> GapItem:
    return GapItem(
        cause=cause,
        category=Category.GROCERIES,
        target=target,
        planned=planned,
        actual=actual,
        operation_count=len(actual),
        missed=missed,
        latest_paid=latest_paid,
    )


def _fix_of(item: GapItem) -> GapFix | None:
    return _fix(item, PlanGaps(_MONTHS, (item,)), _CONTEXT)


class TestFixes:
    """The button under a row, when the correction is clear."""

    def test_budget_over_most_months_is_set_to_its_average(self) -> None:
        """The split opens from this month at the average spent."""
        fix = _fix_of(
            _item(
                GapCause.BUDGET,
                (-470.0, -500.0, -380.0, -530.0),
                target=_groceries_budget(),
                planned=(-400.0,) * 4,
            )
        )

        split = (
            ("split_date", "2026-11-01"),
            ("split_amount", "-470"),
            ("return_to", "/trends#gaps"),
        )
        assert fix == GapFix(
            label="Set the budget to 470\u00a0EUR",
            question="From 01/11/2026: 400\u00a0EUR → 470\u00a0EUR."
            " Past months keep their plan.",
            action="/targets/budget/1/split",
            fields=split,
            url="/targets/budget/1?split_date=2026-11-01&split_amount=-470"
            "&return_to=%2Ftrends%23gaps#split",
        )

    def test_yearly_budget_is_set_by_the_year(self) -> None:
        """The months hold a twelfth of a yearly budget; the fix is yearly."""
        yearly = Budget(
            record_id=3,
            description="Clothes",
            amount=Amount(-1200.0, "EUR"),
            category=Category.CLOTHING,
            date_range=RecurringDateRange(
                DateRange(date(2026, 1, 1), relativedelta(years=1)),
                relativedelta(years=1),
            ),
        )
        monthly_plan = tuple(-1200.0 * days / 365 for days in (31, 31, 30, 31))
        fix = _fix_of(
            _item(
                GapCause.BUDGET,
                tuple(1.5 * planned for planned in monthly_plan),
                target=yearly,
                planned=monthly_plan,
            )
        )

        assert fix is not None
        assert ("split_amount", "-1800") in fix.fields
        # A yearly budget takes the new amount from its next year.
        assert fix.question.startswith("From 01/01/2027: 1\u202f200\u00a0EUR")

    def test_budget_off_both_ways_gets_no_fix(self) -> None:
        """One big month over is not a budget set too low."""
        assert (
            _fix_of(
                _item(
                    GapCause.BUDGET,
                    (-900.0, -390.0, -380.0, -370.0),
                    target=_groceries_budget(),
                    planned=(-400.0,) * 4,
                )
            )
            is None
        )

    def test_budget_already_at_its_average_gets_no_fix(self) -> None:
        """Rounded to the euro, the average is the amount already planned."""
        assert (
            _fix_of(
                _item(
                    GapCause.BUDGET,
                    (-410.0, -390.0, -401.0, -400.0),
                    target=_groceries_budget(),
                    planned=(-400.0,) * 4,
                )
            )
            is None
        )

    def test_ended_budget_gets_no_fix(self) -> None:
        """A budget with no period left to split keeps its past as it is."""
        ended = _groceries_budget().split_at(date(2026, 11, 1))[0]

        assert (
            _fix_of(
                _item(
                    GapCause.BUDGET,
                    (-470.0,) * 4,
                    target=ended,
                    planned=(-400.0,) * 4,
                )
            )
            is None
        )

    def test_planned_amount_follows_the_latest_payment(self) -> None:
        """The split takes what paid the latest occurrence, to the cent."""
        fix = _fix_of(
            _item(
                GapCause.OTHER_AMOUNT,
                (-85.0, -85.0, -95.5, -95.5),
                target=_electricity(),
                planned=(-85.0,) * 4,
                latest_paid=-95.5,
            )
        )

        assert fix == GapFix(
            label="Set the planned amount to 96\u00a0EUR",
            question="From 05/11/2026: 85\u00a0EUR → 95,50\u00a0EUR."
            " Past months keep their plan.",
            action="/targets/planned/2/split",
            fields=(
                ("split_date", "2026-11-01"),
                ("split_amount", "-95.50"),
                ("return_to", "/trends#gaps"),
            ),
            url="/targets/planned/2?split_date=2026-11-01&split_amount=-95.50"
            "&return_to=%2Ftrends%23gaps#split",
        )

    def test_small_gap_gets_no_fix(self) -> None:
        """Two euros a month is not worth changing the plan for."""
        assert (
            _fix_of(
                _item(
                    GapCause.OTHER_AMOUNT,
                    (-87.0,) * 4,
                    target=_electricity(),
                    planned=(-85.0,) * 4,
                    latest_paid=-87.0,
                )
            )
            is None
        )

    def test_latest_payment_on_plan_gets_no_fix(self) -> None:
        """A gap the latest payment no longer shows needs no new amount."""
        assert (
            _fix_of(
                _item(
                    GapCause.OTHER_AMOUNT,
                    (-95.0, -85.0, -85.0, -85.0),
                    target=_electricity(),
                    planned=(-85.0,) * 4,
                    latest_paid=-85.0,
                )
            )
            is None
        )

    def test_two_last_occurrences_unpaid_offers_to_end(self) -> None:
        """The edit page opens on its End button."""
        fix = _fix_of(
            _item(
                GapCause.NOT_PAID,
                (0.0,) * 4,
                target=_electricity(),
                planned=(0.0, 0.0, -85.0, -85.0),
                missed=(date(2026, 9, 5), date(2026, 10, 5)),
            )
        )

        assert fix == GapFix(
            label="Stop planning it",
            question="End today? Later occurrences leave the forecast.",
            action="/targets/planned/2/end",
            fields=(("return_to", "/trends#gaps"),),
        )

    def test_one_unpaid_occurrence_is_not_an_end(self) -> None:
        """A single miss before a payment is a missed link, not a stopped payment."""
        assert (
            _fix_of(
                _item(
                    GapCause.NOT_PAID,
                    (0.0,) * 4,
                    target=_electricity(),
                    planned=(0.0, 0.0, -85.0, 0.0),
                    missed=(date(2026, 9, 5),),
                )
            )
            is None
        )

    def test_planned_operation_already_ended_gets_no_end(self) -> None:
        """Nothing is left to end."""
        assert (
            _fix_of(
                _item(
                    GapCause.NOT_PAID,
                    (0.0,) * 4,
                    target=_electricity(last=date(2026, 10, 5)),
                    planned=(0.0, 0.0, -85.0, -85.0),
                    missed=(date(2026, 9, 5), date(2026, 10, 5)),
                )
            )
            is None
        )

    def test_unplanned_spending_most_months_gets_a_budget(self) -> None:
        """The new budget takes the category and the average per month."""
        fix = _fix_of(_item(GapCause.UNPLANNED_EXPENSE, (-100.0, 0.0, -150.0, -230.0)))

        assert fix == GapFix(
            label="Create a monthly budget of 120\u00a0EUR",
            url="/targets/budget/new?category=GROCERIES&amount=-120"
            "&return_to=%2Ftrends%23gaps",
        )

    def test_one_off_spending_gets_no_budget(self) -> None:
        """A single month of spending is not a habit."""
        assert (
            _fix_of(_item(GapCause.UNPLANNED_EXPENSE, (-480.0, 0.0, 0.0, 0.0))) is None
        )

    def test_uncategorized_spending_gets_no_budget(self) -> None:
        """The fix there is to categorize, not to plan."""
        assert (
            _fix_of(
                _item(GapCause.UNPLANNED_EXPENSE, (-100.0,) * 4)._replace(
                    category=Category.UNCATEGORIZED
                )
            )
            is None
        )
