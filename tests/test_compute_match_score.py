"""Tests for the operation link service."""

from datetime import datetime

from dateutil.relativedelta import relativedelta

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_link_service import compute_match_score
from budget_forecaster.operation_range.operation_range import OperationRange
from budget_forecaster.time_range import TimeRange
from budget_forecaster.types import Category


class TestComputeMatchScore:
    """Tests for the compute_match_score function."""

    def test_perfect_match_score(self) -> None:
        """Test that a perfect match returns high score (minus description if no hints)."""
        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )

        # Perfect match on amount, date, category (no description hints)
        # Should get 40 + 30 + 20 = 90 (no description points without hints)
        score = compute_match_score(operation, op_range, datetime(2023, 1, 15))
        assert score == 90.0

    def test_perfect_match_with_description_hints(self) -> None:
        """Test that matching description hints adds to score."""
        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        operation = HistoricOperation(
            unique_id=1,
            description="GROCERIES STORE ABC",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )

        # Perfect match including description
        score = compute_match_score(
            operation,
            op_range,
            datetime(2023, 1, 15),
            description_hints={"GROCERIES", "ABC"},
        )
        assert score == 100.0

    def test_category_mismatch_reduces_score(self) -> None:
        """Test that wrong category reduces score by 20 points."""
        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        operation = HistoricOperation(
            unique_id=1,
            description="Test",
            amount=Amount(100.0),
            category=Category.OTHER,  # Wrong category
            date=datetime(2023, 1, 15),
        )

        score = compute_match_score(operation, op_range, datetime(2023, 1, 15))
        # Should get 40 (amount) + 30 (date) + 0 (category) = 70
        assert score == 70.0

    def test_amount_tolerance_within_range(self) -> None:
        """Test that amount within tolerance gets full points."""
        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        # 5% tolerance means 95-105 should get full amount score
        operation = HistoricOperation(
            unique_id=1,
            description="Test",
            amount=Amount(105.0),  # At tolerance boundary
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )

        score = compute_match_score(operation, op_range, datetime(2023, 1, 15))
        assert score == 90.0  # Full score (40 + 30 + 20)

    def test_amount_beyond_tolerance_reduces_score(self) -> None:
        """Test that amount beyond tolerance reduces score."""
        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        # 20% difference is 15% beyond 5% tolerance
        operation = HistoricOperation(
            unique_id=1,
            description="Test",
            amount=Amount(120.0),  # 20% off
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )

        score = compute_match_score(operation, op_range, datetime(2023, 1, 15))
        # Amount score: 40 * (1 - 0.15) = 34
        # Date score: 30
        # Category score: 20
        assert 80.0 < score < 90.0

    def test_date_beyond_tolerance_reduces_score(self) -> None:
        """Test that date beyond tolerance reduces score."""
        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        # 20 days from iteration is 15 days beyond 5 day tolerance
        operation = HistoricOperation(
            unique_id=1,
            description="Test",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 21),  # 20 days from iteration
        )

        score = compute_match_score(operation, op_range, datetime(2023, 1, 1))
        # Amount score: 40
        # Date score: 30 * (1 - 15/30) = 15
        # Category score: 20
        assert score == 75.0

    def test_complete_mismatch_low_score(self) -> None:
        """Test that a complete mismatch returns low score."""
        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        operation = HistoricOperation(
            unique_id=1,
            description="Completely different",
            amount=Amount(1000.0),  # 10x different
            category=Category.OTHER,
            date=datetime(2023, 6, 15),  # 165+ days away
        )

        score = compute_match_score(operation, op_range, datetime(2023, 1, 1))
        # Amount: way beyond tolerance -> 0
        # Date: way beyond tolerance -> 0
        # Category: mismatch -> 0
        assert score == 0.0

    def test_custom_tolerance_parameters(self) -> None:
        """Test that custom tolerance parameters are respected."""
        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        operation = HistoricOperation(
            unique_id=1,
            description="Test",
            amount=Amount(110.0),  # 10% off
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )

        # With default 5% tolerance, this would reduce amount score
        score_default = compute_match_score(operation, op_range, datetime(2023, 1, 15))

        # With 10% tolerance, should get full amount score
        score_relaxed = compute_match_score(
            operation,
            op_range,
            datetime(2023, 1, 15),
            approximation_amount_ratio=0.10,
        )

        assert score_relaxed > score_default
        assert score_relaxed == 90.0  # Full score with relaxed tolerance
