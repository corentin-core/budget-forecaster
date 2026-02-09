"""Tests for HistoricOperation."""

from datetime import date

import pytest

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.historic_operation import HistoricOperation


def _make_op(
    unique_id: int = 1,
    description: str = "CARTE CARREFOUR",
    amount: float = -50.0,
    operation_date: date = date(2025, 1, 15),
    category: Category = Category.GROCERIES,
) -> HistoricOperation:
    return HistoricOperation(
        unique_id=unique_id,
        description=description,
        amount=Amount(amount),
        category=category,
        operation_date=operation_date,
    )


class TestEquality:
    """Tests for HistoricOperation repr, equality and comparison."""

    def test_repr_contains_id_and_details(self) -> None:
        """repr includes the unique_id and operation details."""
        op = _make_op(unique_id=42, description="AMAZON", amount=-99.0)
        result = repr(op)
        assert "42" in result
        assert "AMAZON" in result

    def test_equal_operations(self) -> None:
        """Two operations with same id and data are equal."""
        op1 = _make_op()
        op2 = _make_op()
        assert op1 == op2

    def test_not_equal_different_id(self) -> None:
        """Operations with different ids are not equal."""
        op1 = _make_op(unique_id=1)
        op2 = _make_op(unique_id=2)
        assert op1 != op2

    def test_eq_with_non_historic_operation_returns_not_implemented(self) -> None:
        """Equality with a non-HistoricOperation returns NotImplemented."""
        op = _make_op()
        assert op != "not an operation"

    def test_lt_with_non_historic_operation_returns_not_implemented(self) -> None:
        """Comparison with a non-HistoricOperation returns NotImplemented."""
        op = _make_op()
        with pytest.raises(TypeError):
            _ = op < "not an operation"  # type: ignore[operator]


class TestHash:
    """Tests for HistoricOperation.__hash__."""

    def test_equal_operations_have_same_hash(self) -> None:
        """Equal operations produce the same hash."""
        op1 = _make_op()
        op2 = _make_op()
        assert hash(op1) == hash(op2)

    def test_different_operations_have_different_hash(self) -> None:
        """Operations with different ids produce different hashes."""
        op1 = _make_op(unique_id=1)
        op2 = _make_op(unique_id=2)
        assert hash(op1) != hash(op2)

    def test_usable_in_set(self) -> None:
        """HistoricOperations can be used in sets."""
        op1 = _make_op(unique_id=1)
        op2 = _make_op(unique_id=2)
        op1_dup = _make_op(unique_id=1)
        assert len({op1, op2, op1_dup}) == 2


class TestReplace:
    """Tests for HistoricOperation.replace."""

    def test_replace_category(self) -> None:
        """replace() with category returns new operation with updated category."""
        op = _make_op(category=Category.UNCATEGORIZED)
        replaced = op.replace(category=Category.GROCERIES)

        assert replaced.category == Category.GROCERIES
        assert replaced.unique_id == op.unique_id
        assert replaced.description == op.description

    def test_replace_description(self) -> None:
        """replace() with description returns new operation."""
        op = _make_op(description="OLD")
        replaced = op.replace(description="NEW")

        assert replaced.description == "NEW"
        assert replaced.unique_id == op.unique_id
