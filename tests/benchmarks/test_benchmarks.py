"""Performance benchmarks for budget-forecaster core components."""

from datetime import date, timedelta

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import (
    DateRange,
    RecurringDateRange,
    RecurringDay,
    SingleDay,
)
from budget_forecaster.core.types import Category
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.forecast.forecast_actualizer import ForecastActualizer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def recurring_date_range() -> RecurringDateRange:
    """A monthly recurring date range spanning two years."""
    base = DateRange(date(2025, 1, 1), relativedelta(months=1))
    return RecurringDateRange(
        initial_date_range=base,
        period=relativedelta(months=1),
        expiration_date=date(2026, 12, 31),
    )


@pytest.fixture
def planned_operations() -> tuple[PlannedOperation, ...]:
    """A realistic set of planned operations."""
    ops = []
    descriptions = [
        ("Rent", -1200.0, Category.RENT),
        ("Salary", 3500.0, Category.SALARY),
        ("Electricity", -80.0, Category.ELECTRICITY),
        ("Internet", -40.0, Category.INTERNET),
        ("Car insurance", -95.0, Category.CAR_INSURANCE),
        ("House insurance", -35.0, Category.HOUSE_INSURANCE),
        ("Phone", -25.0, Category.PHONE),
        ("Savings", -500.0, Category.SAVINGS),
        ("House loan", -800.0, Category.HOUSE_LOAN),
        ("Childcare", -350.0, Category.CHILDCARE),
    ]
    for i, (desc, amount, cat) in enumerate(descriptions):
        ops.append(
            PlannedOperation(
                record_id=i + 1,
                description=desc,
                amount=Amount(amount, "EUR"),
                category=cat,
                date_range=RecurringDay(
                    start_date=date(2025, 1, 5 + i),
                    period=relativedelta(months=1),
                    expiration_date=date(2026, 12, 31),
                ),
            )
        )
    return tuple(ops)


@pytest.fixture
def budgets() -> tuple[Budget, ...]:
    """A realistic set of budgets."""
    budget_defs = [
        ("Groceries", -600.0, Category.GROCERIES),
        ("Leisure", -200.0, Category.LEISURE),
        ("Clothing", -100.0, Category.CLOTHING),
        ("Health care", -80.0, Category.HEALTH_CARE),
        ("Gifts", -50.0, Category.GIFTS),
    ]
    result = []
    for i, (desc, amount, cat) in enumerate(budget_defs):
        base_range = DateRange(date(2025, 1, 1), relativedelta(months=1))
        result.append(
            Budget(
                record_id=100 + i,
                description=desc,
                amount=Amount(amount, "EUR"),
                category=cat,
                date_range=RecurringDateRange(
                    initial_date_range=base_range,
                    period=relativedelta(months=1),
                    expiration_date=date(2026, 12, 31),
                ),
            )
        )
    return tuple(result)


@pytest.fixture
def historic_operations() -> tuple[HistoricOperation, ...]:
    """Generate 12 months of historic operations."""
    ops: list[HistoricOperation] = []
    uid = 1
    categories_amounts = [
        (Category.RENT, -1200.0),
        (Category.SALARY, 3500.0),
        (Category.ELECTRICITY, -80.0),
        (Category.GROCERIES, -550.0),
        (Category.LEISURE, -180.0),
        (Category.INTERNET, -40.0),
        (Category.PHONE, -25.0),
        (Category.CAR_INSURANCE, -95.0),
        (Category.SAVINGS, -500.0),
        (Category.HOUSE_LOAN, -800.0),
    ]
    for month_offset in range(12):
        for cat, amount in categories_amounts:
            op_date = date(2025, 1, 10) + relativedelta(months=month_offset)
            ops.append(
                HistoricOperation(
                    unique_id=uid,
                    description=f"{cat.name} payment",
                    amount=Amount(amount, "EUR"),
                    category=cat,
                    operation_date=op_date,
                )
            )
            uid += 1
    return tuple(ops)


@pytest.fixture
def account(historic_operations: tuple[HistoricOperation, ...]) -> Account:
    """An account with historic operations."""
    return Account(
        name="Main account",
        balance=5000.0,
        currency="EUR",
        balance_date=date(2025, 6, 15),
        operations=historic_operations,
    )


@pytest.fixture
def forecast(
    planned_operations: tuple[PlannedOperation, ...],
    budgets: tuple[Budget, ...],
) -> Forecast:
    return Forecast(operations=planned_operations, budgets=budgets)


# ---------------------------------------------------------------------------
# Benchmarks — Core
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_bench_amount_arithmetic(benchmark) -> None:
    """Benchmark Amount arithmetic chain."""

    def run():
        a = Amount(1500.0, "EUR")
        b = Amount(350.0, "EUR")
        for _ in range(200):
            c = a + b
            c = c - b
            c = c * 2.5
            c = -c
            _ = abs(c)

    benchmark(run)


@pytest.mark.benchmark
def test_bench_date_range_iterate(
    benchmark, recurring_date_range: RecurringDateRange
) -> None:
    """Benchmark iterating over a recurring date range (24 months)."""

    def run():
        for _ in recurring_date_range.iterate_over_date_ranges():
            pass

    benchmark(run)


@pytest.mark.benchmark
def test_bench_date_range_current_lookup(
    benchmark, recurring_date_range: RecurringDateRange
) -> None:
    """Benchmark finding the current date range for various target dates."""

    targets = [date(2025, 1, 1) + timedelta(days=i * 30) for i in range(24)]

    def run():
        for t in targets:
            recurring_date_range.current_date_range(t)

    benchmark(run)


@pytest.mark.benchmark
def test_bench_operation_range_amount_on_period(
    benchmark, planned_operations: tuple[PlannedOperation, ...]
) -> None:
    """Benchmark amount_on_period across all planned operations for 12 months."""

    months = [
        (
            date(2025, 1, 1) + relativedelta(months=m),
            date(2025, 1, 1) + relativedelta(months=m + 1) - timedelta(days=1),
        )
        for m in range(12)
    ]

    def run():
        for start, end in months:
            for op in planned_operations:
                op.amount_on_period(start, end)

    benchmark(run)


@pytest.mark.benchmark
def test_bench_forecast_actualizer(
    benchmark,
    account: Account,
    forecast: Forecast,
) -> None:
    """Benchmark the ForecastActualizer with no operation links."""

    def run():
        actualizer = ForecastActualizer(account, operation_links=())
        actualizer(forecast)

    benchmark(run)


@pytest.mark.benchmark
def test_bench_historic_operation_sorting(
    benchmark, historic_operations: tuple[HistoricOperation, ...]
) -> None:
    """Benchmark sorting a large set of historic operations by date."""
    ops_list = list(historic_operations)

    def run():
        sorted(ops_list, key=lambda op: op.operation_date)

    benchmark(run)


@pytest.mark.benchmark
def test_bench_budget_amount_on_period(benchmark, budgets: tuple[Budget, ...]) -> None:
    """Benchmark budget amount_on_period across 12 months."""

    months = [
        (
            date(2025, 1, 1) + relativedelta(months=m),
            date(2025, 1, 1) + relativedelta(months=m + 1) - timedelta(days=1),
        )
        for m in range(12)
    ]

    def run():
        for start, end in months:
            for b in budgets:
                b.amount_on_period(start, end)

    benchmark(run)
