"""Tests for the operations listed on a budget or planned operation page."""

import re
from datetime import date
from typing import NamedTuple

from dateutil.relativedelta import relativedelta
from fastapi.testclient import TestClient

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import (
    DateRange,
    RecurringDateRange,
    RecurringDay,
)
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.iteration_resolution import (
    IterationAction,
    IterationResolution,
)
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.web.formatting import format_eur
from budget_forecaster.web.linked_history import (
    HISTORY_STEP_MONTHS,
    MAX_HISTORY_MONTHS,
    OccurrenceState,
    build_linked_history,
)

_BALANCE_DATE = date(2026, 9, 20)


class _Overdue(NamedTuple):
    planned_operation_id: int
    iteration_date: date
    days_overdue: int


class _FakeApp:  # pylint: disable=too-few-public-methods
    """The few ApplicationService reads the history needs."""

    def __init__(
        self,
        operations: tuple[HistoricOperation, ...],
        links: tuple[OperationLink, ...],
        resolutions: tuple[IterationResolution, ...] = (),
        overdue: tuple[_Overdue, ...] = (),
    ) -> None:
        self.balance_date = _BALANCE_DATE
        self.operations = operations
        self._links = links
        self._resolutions = resolutions
        self._overdue = overdue

    def get_links_for_target(self, target: object) -> tuple[OperationLink, ...]:
        """Every link given, whatever the target."""
        del target
        return self._links

    def get_iteration_resolutions(self, op_id: int) -> tuple[IterationResolution, ...]:
        """The decisions given."""
        del op_id
        return self._resolutions

    def get_overdue_iterations(self) -> tuple[_Overdue, ...]:
        """The overdue occurrences given."""
        return self._overdue


def _operation(op_id: int, day: date, amount: float) -> HistoricOperation:
    return HistoricOperation(
        unique_id=op_id,
        description=f"OPERATION {op_id}",
        amount=Amount(amount, "EUR"),
        category=Category.RENT,
        operation_date=day,
    )


def _link(op_id: int, target_type: LinkType, iteration: date) -> OperationLink:
    return OperationLink(
        operation_unique_id=op_id,
        target_type=target_type,
        target_id=1,
        iteration_date=iteration,
    )


def _rent(
    start: date = date(2026, 1, 5), until: date | None = None
) -> PlannedOperation:
    return PlannedOperation(
        record_id=1,
        description="Rent",
        amount=Amount(-800.0, "EUR"),
        category=Category.RENT,
        date_range=RecurringDay(start, relativedelta(months=1), until),
    )


def _groceries(months_per_period: int = 1) -> Budget:
    return Budget(
        record_id=1,
        description="Groceries",
        amount=Amount(-400.0, "EUR"),
        category=Category.GROCERIES,
        date_range=RecurringDateRange(
            DateRange(date(2026, 1, 1), relativedelta(months=months_per_period)),
            relativedelta(months=months_per_period),
        ),
    )


class TestPlannedOperation:
    """One row per occurrence, most recent first."""

    def test_states_of_the_occurrences(self) -> None:
        """Paid, late on the Accueil card, decided, and the next one ahead."""
        app = _FakeApp(
            operations=(_operation(10, date(2026, 9, 4), -800.0),),
            links=(_link(10, LinkType.PLANNED_OPERATION, date(2026, 9, 5)),),
            resolutions=(
                IterationResolution(
                    planned_operation_id=1,
                    iteration_date=date(2026, 7, 5),
                    action=IterationAction.POSTPONE,
                    postponed_to=date(2026, 7, 20),
                ),
                IterationResolution(
                    planned_operation_id=1,
                    iteration_date=date(2026, 6, 5),
                    action=IterationAction.SKIP,
                ),
            ),
            overdue=(_Overdue(1, date(2026, 8, 5), 46),),
        )
        history = build_linked_history(app, _rent(), 4)  # type: ignore[arg-type]

        rows = [(o.start, o.state, o.days_late) for o in history.occurrences]
        assert rows == [
            (date(2026, 10, 5), OccurrenceState.UPCOMING, None),
            (date(2026, 9, 5), OccurrenceState.LINKED, None),
            (date(2026, 8, 5), OccurrenceState.NOT_LINKED, 46),
            (date(2026, 7, 5), OccurrenceState.POSTPONED, None),
            (date(2026, 6, 5), OccurrenceState.SKIPPED, None),
        ]
        paid = history.occurrences[1]
        assert [op.operation_id for op in paid.operations] == [10]
        assert paid.total == -800.0
        assert history.occurrences[3].postponed_to == date(2026, 7, 20)

    def test_operation_paid_ahead_shows_the_next_occurrence_too(self) -> None:
        """An occurrence paid before it is due does not hide the one after it."""
        app = _FakeApp(
            operations=(_operation(10, date(2026, 9, 30), -800.0),),
            links=(_link(10, LinkType.PLANNED_OPERATION, date(2026, 10, 5)),),
        )
        history = build_linked_history(app, _rent(), 1)  # type: ignore[arg-type]

        assert [(o.start, o.state) for o in history.occurrences] == [
            (date(2026, 11, 5), OccurrenceState.UPCOMING),
            (date(2026, 10, 5), OccurrenceState.LINKED),
            (date(2026, 9, 5), OccurrenceState.NOT_LINKED),
        ]

    def test_link_to_an_occurrence_the_target_no_longer_has(self) -> None:
        """A link kept after the dates changed still shows its operation."""
        app = _FakeApp(
            operations=(_operation(10, date(2026, 9, 2), -800.0),),
            links=(_link(10, LinkType.PLANNED_OPERATION, date(2026, 9, 1)),),
        )
        history = build_linked_history(app, _rent(), 1)  # type: ignore[arg-type]

        stale = [o for o in history.occurrences if o.start == date(2026, 9, 1)]
        assert len(stale) == 1
        assert stale[0].state is OccurrenceState.LINKED

    def test_window_and_show_more(self) -> None:
        """The window starts on the first of a month; older occurrences wait."""
        app = _FakeApp(operations=(), links=())
        history = build_linked_history(app, _rent(), 3)  # type: ignore[arg-type]

        assert min(o.start for o in history.occurrences) == date(2026, 7, 5)
        assert history.more_months == 3 + HISTORY_STEP_MONTHS

    def test_no_show_more_when_everything_fits(self) -> None:
        """A target that started inside the window has nothing older."""
        app = _FakeApp(operations=(), links=())
        history = build_linked_history(
            app, _rent(date(2026, 8, 5)), 3  # type: ignore[arg-type]
        )

        assert history.more_months is None

    def test_ended_target_shows_its_last_months(self) -> None:
        """The window of an ended target ends where the target ends."""
        app = _FakeApp(operations=(), links=())
        history = build_linked_history(
            app, _rent(date(2020, 1, 5), until=date(2024, 6, 30)), 2  # type: ignore[arg-type]
        )

        assert [o.start for o in history.occurrences] == [
            date(2024, 6, 5),
            date(2024, 5, 5),
        ]
        assert history.more_months == 2 + HISTORY_STEP_MONTHS

    def test_no_show_more_at_the_cap(self) -> None:
        """At the widest window, asking for more would reload the same page."""
        app = _FakeApp(operations=(), links=())
        history = build_linked_history(
            app, _rent(date(2000, 1, 5)), MAX_HISTORY_MONTHS + 50  # type: ignore[arg-type]
        )

        assert history.months == MAX_HISTORY_MONTHS
        assert history.more_months is None


class TestBudget:
    """One row per period, with what was spent against the budget."""

    def test_periods_up_to_the_running_one(self) -> None:
        """Past periods carry their total; the running one is in progress."""
        app = _FakeApp(
            operations=(
                _operation(10, date(2026, 8, 3), -120.0),
                _operation(11, date(2026, 8, 20), -80.0),
                _operation(12, date(2026, 9, 2), -50.0),
            ),
            links=(
                _link(10, LinkType.BUDGET, date(2026, 8, 1)),
                _link(11, LinkType.BUDGET, date(2026, 8, 1)),
                _link(12, LinkType.BUDGET, date(2026, 9, 1)),
            ),
        )
        history = build_linked_history(app, _groceries(), 3)  # type: ignore[arg-type]

        rows = [(o.label, o.state, o.total) for o in history.occurrences]
        assert rows == [
            ("September 2026", OccurrenceState.IN_PROGRESS, -50.0),
            ("August 2026", OccurrenceState.LINKED, -200.0),
            ("July 2026", OccurrenceState.NOT_LINKED, 0.0),
        ]
        assert history.occurrences[1].planned == -400.0

    def test_multi_month_period(self) -> None:
        """A link dated inside a two-month period counts for that period."""
        app = _FakeApp(
            operations=(_operation(10, date(2026, 8, 10), -90.0),),
            links=(_link(10, LinkType.BUDGET, date(2026, 8, 10)),),
        )
        history = build_linked_history(
            app, _groceries(months_per_period=2), 3  # type: ignore[arg-type]
        )

        period = next(o for o in history.occurrences if o.start == date(2026, 7, 1))
        assert period.label == "01/07/2026 → 31/08/2026"
        assert period.end == date(2026, 8, 31)
        assert period.total == -90.0

    def test_refund_is_not_spending(self) -> None:
        """A refund larger than the spending leaves nothing consumed."""
        app = _FakeApp(
            operations=(
                _operation(10, date(2026, 8, 3), -50.0),
                _operation(11, date(2026, 8, 9), 80.0),
            ),
            links=(
                _link(10, LinkType.BUDGET, date(2026, 8, 1)),
                _link(11, LinkType.BUDGET, date(2026, 8, 1)),
            ),
        )
        history = build_linked_history(app, _groceries(), 2)  # type: ignore[arg-type]

        august = next(o for o in history.occurrences if o.start == date(2026, 8, 1))
        assert (august.total, august.consumed) == (30.0, 0.0)

    def test_link_outside_every_period(self) -> None:
        """A link a date change left outside the periods keeps its operation."""
        app = _FakeApp(
            operations=(_operation(10, date(2026, 9, 2), -40.0),),
            links=(_link(10, LinkType.BUDGET, date(2025, 12, 15)),),
        )
        # Ten-day periods from the 1st: the 15th falls between two of them.
        budget = Budget(
            record_id=1,
            description="Groceries",
            amount=Amount(-400.0, "EUR"),
            category=Category.GROCERIES,
            date_range=RecurringDateRange(
                DateRange(date(2025, 12, 1), relativedelta(days=10)),
                relativedelta(months=1),
            ),
        )
        history = build_linked_history(app, budget, 12)  # type: ignore[arg-type]

        orphan = [o for o in history.occurrences if o.start == date(2025, 12, 15)]
        assert [op.operation_id for op in orphan[0].operations] == [10]

    def test_straddling_period_offers_nothing_older(self) -> None:
        """A first period already shown in full leaves nothing to show more of."""
        app = _FakeApp(operations=(), links=())
        budget = Budget(
            record_id=1,
            description="Holidays",
            amount=Amount(-1000.0, "EUR"),
            category=Category.GROCERIES,
            date_range=RecurringDateRange(
                DateRange(date(2026, 7, 1), relativedelta(months=2)),
                relativedelta(months=2),
            ),
        )
        history = build_linked_history(app, budget, 2)  # type: ignore[arg-type]

        assert date(2026, 7, 1) in [o.start for o in history.occurrences]
        assert history.more_months is None


class TestHistoryPage:
    """The card on the history page of the demo database."""

    def test_budget_page_lists_its_operations(self, client: TestClient) -> None:
        """Each linked operation opens its detail page."""
        html = client.get("/targets/budget/1/history").text

        card = html[html.index('id="linked"') :]
        assert "/operations/" in card
        assert "linked-period" in card

    def test_history_is_bounded(self, client: TestClient) -> None:
        """A hand-typed window, too wide or not a number, still renders."""
        assert client.get("/targets/planned/1/history?months=100000").status_code == 200
        assert client.get("/targets/planned/1/history?months=abc").status_code == 200

    def test_late_occurrence_says_how_late(self, client: TestClient) -> None:
        """An occurrence on the Accueil card reads as late and offers the picker."""
        home = client.get("/").text
        found = re.search(r"/overdue/(\d+)/([\d-]+)/link", home)
        assert found, "the demo should have an overdue occurrence"
        op_id, iteration = found.groups()

        card = client.get(f"/targets/planned/{op_id}/history").text
        card = card[card.index('id="linked"') :]
        assert "linked-state not_linked late" in card
        assert f"/overdue/{op_id}/{iteration}/link" in card

    def test_paid_occurrence_compares_with_the_plan(self, client: TestClient) -> None:
        """A payment that differs from the plan shows both amounts."""
        card = client.get("/targets/planned/1/history").text
        card = card[card.index('id="linked"') :]

        assert f"pour {format_eur(3200.0, 'EUR')} prévus" in card

    def test_every_unlinked_occurrence_offers_the_picker(
        self, client: TestClient
    ) -> None:
        """An unlinked occurrence past the Accueil window still has "Lier…"."""
        card = client.get("/targets/planned/1/history?months=24").text
        card = card[card.index('id="linked"') :]

        assert card.count("Non lié") == card.count("/link?return_to=")

    def test_budget_period_searches_the_ledger(self, client: TestClient) -> None:
        """A period opens the ledger on its unlinked operations, with a way back."""
        card = client.get("/targets/budget/1/history").text
        card = card[card.index('id="linked"') :]
        start = card.index('href="/operations?category=') + len('href="')
        url = card[start : card.index('"', start)].replace("&amp;", "&")

        ledger = client.get(url).text
        assert "unlinked=true" in url
        assert re.search(r'value="groceries"\s*selected', ledger)
        assert 'class="back"><a href="/targets/budget/1/history?' in ledger
