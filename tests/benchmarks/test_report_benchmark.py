"""Benchmarks for report generation pipeline.

Uses the demo data generator to create a realistic dataset, then benchmarks
the most expensive computations in the report pipeline.

Run locally (validation only, no measurements):
    pytest tests/benchmarks/ --codspeed

Actual measurements happen in CI via CodSpeed's instrumented runner.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.services.account.account_analyzer import AccountAnalyzer
from budget_forecaster.services.forecast.forecast_service import ForecastService
from examples.generate_demo import generate_demo_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def demo_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a temporary demo database for benchmarks."""
    db_path = tmp_path_factory.mktemp("bench") / "bench.db"
    generate_demo_db(db_path, account_name="Benchmark", seed=42)
    return db_path


@pytest.fixture(scope="module")
def pipeline(
    demo_db: Path,
) -> tuple[PersistentAccount, ForecastService, tuple[OperationLink, ...]]:
    """Set up the full pipeline from DB: repo -> account -> forecast service."""
    repo = SqliteRepository(demo_db)
    repo.initialize()
    persistent_account = PersistentAccount(repo)
    service = ForecastService(persistent_account, repo)
    service.load_forecast()
    links = repo.get_all_links()
    return persistent_account, service, links


@pytest.fixture(scope="module")
def analyzer_inputs(
    pipeline: tuple[PersistentAccount, ForecastService, tuple[OperationLink, ...]],
) -> tuple[Account, Forecast, tuple[OperationLink, ...], date, date]:
    """Prepare inputs for direct AccountAnalyzer benchmarks."""
    persistent_account, service, links = pipeline
    account = persistent_account.account
    forecast = service.load_forecast()

    start_date = date.today() - relativedelta(months=4)
    end_date = date.today() + relativedelta(months=12)
    return account, forecast, links, start_date, end_date


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_compute_report(
    benchmark: pytest.BenchmarkFixture,
    pipeline: tuple[PersistentAccount, ForecastService, tuple[OperationLink, ...]],
) -> None:
    """Benchmark the full report pipeline (end-to-end)."""
    _, service, links = pipeline

    benchmark(service.compute_report, operation_links=links)


@pytest.mark.benchmark
def test_compute_budget_forecast(
    benchmark: pytest.BenchmarkFixture,
    analyzer_inputs: tuple[Account, Forecast, tuple[OperationLink, ...], date, date],
) -> None:
    """Benchmark compute_budget_forecast — the most expensive sub-computation.

    Involves 6+ passes over data, dict accumulation, and pandas MultiIndex reshaping.
    """
    account, forecast, links, start_date, end_date = analyzer_inputs
    analyzer = AccountAnalyzer(account, forecast, links)

    benchmark(analyzer.compute_budget_forecast, start_date, end_date)


@pytest.mark.benchmark
def test_compute_balance_evolution(
    benchmark: pytest.BenchmarkFixture,
    analyzer_inputs: tuple[Account, Forecast, tuple[OperationLink, ...], date, date],
) -> None:
    """Benchmark compute_balance_evolution_per_day — day-by-day simulation."""
    account, forecast, links, start_date, end_date = analyzer_inputs
    analyzer = AccountAnalyzer(account, forecast, links)

    benchmark(analyzer.compute_balance_evolution_per_day, start_date, end_date)
