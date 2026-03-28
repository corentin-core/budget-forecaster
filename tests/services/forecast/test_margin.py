"""Tests for margin computation in ForecastService."""
# pylint: disable=too-few-public-methods

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from freezegun import freeze_time

from budget_forecaster.domain.account.account import Account
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.services.account.account_analysis_report import (
    AccountAnalysisReport,
)
from budget_forecaster.services.forecast.forecast_service import ForecastService


class _AccountStub:
    """AccountInterface stub for unit tests."""

    def __init__(self, account: Account) -> None:
        self._account = account

    @property
    def account(self) -> Account:
        """Return the account."""
        return self._account


@pytest.fixture(name="mock_account")
def mock_account_fixture() -> Account:
    """Create a mock account."""
    return Account(
        name="Test Account",
        balance=3000.0,
        currency="EUR",
        balance_date=date(2026, 1, 1),
        operations=(),
    )


@pytest.fixture(name="repository")
def repository_fixture(tmp_path: Path) -> Iterator[RepositoryInterface]:
    """Create an initialized repository."""
    with SqliteRepository(tmp_path / "test.db") as repo:
        yield repo


@pytest.fixture(name="service")
def service_fixture(
    mock_account: Account,
    repository: RepositoryInterface,
) -> ForecastService:
    """Create a ForecastService."""
    return ForecastService(
        account_provider=_AccountStub(mock_account),
        repository=repository,
    )


def _build_balance_df(data: dict[str, float]) -> pd.DataFrame:
    """Build a balance_evolution_per_day DataFrame from date->balance mapping."""
    index = pd.DatetimeIndex([pd.Timestamp(d) for d in data])
    return pd.DataFrame({"Balance": list(data.values())}, index=index)


def _compute_with_balance(
    service: ForecastService,
    mock_analyzer_class: MagicMock,
    balance_df: pd.DataFrame,
) -> None:
    """Set up mock analyzer to return a report with given balance, then compute."""
    mock_report = MagicMock(spec=AccountAnalysisReport)
    mock_report.balance_evolution_per_day = balance_df

    mock_analyzer = MagicMock()
    mock_analyzer.compute_report.return_value = mock_report
    mock_analyzer_class.return_value = mock_analyzer

    service.compute_report()


class TestGetAvailableMargin:
    """Tests for ForecastService.get_available_margin()."""

    def test_returns_none_without_report(self, service: ForecastService) -> None:
        """Returns None when no report is computed."""
        result = service.get_available_margin(date(2026, 3, 1), threshold=0)
        assert result is None

    @patch("budget_forecaster.services.forecast.forecast_service.AccountAnalyzer")
    def test_basic_margin_no_threshold(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """Margin equals lowest future balance when threshold is 0."""
        balance_df = _build_balance_df(
            {
                "2026-03-01": 3000,
                "2026-03-15": 2500,
                "2026-04-01": 2000,
                "2026-04-15": 1500,
                "2026-05-01": 2200,
            }
        )
        _compute_with_balance(service, mock_analyzer_class, balance_df)

        result = service.get_available_margin(date(2026, 3, 1), threshold=0)

        assert result is not None
        assert result["available_margin"] == 1500
        assert result["balance_at_month_start"] == 3000
        assert result["lowest_balance"] == 1500
        assert result["lowest_balance_date"] == date(2026, 4, 15)
        assert result["threshold"] == 0

    @patch("budget_forecaster.services.forecast.forecast_service.AccountAnalyzer")
    def test_margin_with_threshold(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """Margin is lowest balance minus threshold."""
        balance_df = _build_balance_df(
            {
                "2026-03-01": 3000,
                "2026-04-01": 2000,
                "2026-05-01": 1500,
            }
        )
        _compute_with_balance(service, mock_analyzer_class, balance_df)

        result = service.get_available_margin(date(2026, 3, 1), threshold=500)

        assert result is not None
        assert result["available_margin"] == 1000  # 1500 - 500
        assert result["lowest_balance"] == 1500
        assert result["threshold"] == 500

    @patch("budget_forecaster.services.forecast.forecast_service.AccountAnalyzer")
    def test_negative_margin_alert(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """Margin is negative when lowest balance < threshold."""
        balance_df = _build_balance_df(
            {
                "2026-03-01": 800,
                "2026-04-01": 300,
                "2026-05-01": 600,
            }
        )
        _compute_with_balance(service, mock_analyzer_class, balance_df)

        result = service.get_available_margin(date(2026, 3, 1), threshold=500)

        assert result is not None
        assert result["available_margin"] == -200  # 300 - 500
        assert result["lowest_balance"] == 300
        assert result["lowest_balance_date"] == date(2026, 4, 1)

    @patch("budget_forecaster.services.forecast.forecast_service.AccountAnalyzer")
    def test_margin_from_future_month(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """Margin computed from a future month ignores earlier data."""
        balance_df = _build_balance_df(
            {
                "2026-03-01": 3000,
                "2026-03-15": 1000,  # dip in March
                "2026-04-01": 2500,
                "2026-04-15": 2000,
                "2026-05-01": 2200,
            }
        )
        _compute_with_balance(service, mock_analyzer_class, balance_df)

        # Viewing April: March dip is ignored
        result = service.get_available_margin(date(2026, 4, 1), threshold=0)

        assert result is not None
        assert result["available_margin"] == 2000
        assert result["balance_at_month_start"] == 2500
        assert result["lowest_balance_date"] == date(2026, 4, 15)

    @freeze_time("2026-03-28")
    @patch("budget_forecaster.services.forecast.forecast_service.AccountAnalyzer")
    def test_excludes_past_dates_from_lowest_balance(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """Lowest balance ignores past dates within the current month."""
        balance_df = _build_balance_df(
            {
                "2026-03-01": 3000,
                "2026-03-24": 1000,  # past dip (before today 03-28)
                "2026-03-28": 2500,
                "2026-04-01": 2000,
                "2026-04-15": 1800,
            }
        )
        _compute_with_balance(service, mock_analyzer_class, balance_df)

        result = service.get_available_margin(date(2026, 3, 1), threshold=0)

        assert result is not None
        # Past dip at 1000 on 03-24 should be ignored
        assert result["lowest_balance"] == 1800
        assert result["lowest_balance_date"] == date(2026, 4, 15)
        # balance_at_start still reflects month start
        assert result["balance_at_month_start"] == 3000

    @patch("budget_forecaster.services.forecast.forecast_service.AccountAnalyzer")
    def test_returns_none_for_empty_future(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """Returns None when no data exists from the selected month."""
        balance_df = _build_balance_df(
            {
                "2026-03-01": 3000,
                "2026-03-15": 2500,
            }
        )
        _compute_with_balance(service, mock_analyzer_class, balance_df)

        result = service.get_available_margin(date(2026, 6, 1), threshold=0)
        assert result is None


class TestMarginThreshold:
    """Tests for threshold persistence via ForecastService."""

    def test_default_threshold(self, service: ForecastService) -> None:
        """Default threshold is 0."""
        assert service.margin_threshold == 0.0

    def test_set_and_get_threshold(self, service: ForecastService) -> None:
        """Set threshold and read it back."""
        service.margin_threshold = 500.0
        assert service.margin_threshold == 500.0

    def test_update_threshold(self, service: ForecastService) -> None:
        """Updating threshold overwrites previous value."""
        service.margin_threshold = 100.0
        service.margin_threshold = 250.0
        assert service.margin_threshold == 250.0
