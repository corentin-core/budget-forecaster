"""Tests for Amount arithmetic operations."""

import pytest

from budget_forecaster.amount import Amount


class TestAmountAddition:
    """Tests for Amount.__add__."""

    def test_add_same_currency(self) -> None:
        """Test adding two amounts with the same currency."""
        a = Amount(10.0, "EUR")
        b = Amount(5.0, "EUR")
        result = a + b
        assert result.value == 15.0
        assert result.currency == "EUR"

    def test_add_different_currency_raises(self) -> None:
        """Test that adding amounts with different currencies raises ValueError."""
        a = Amount(10.0, "EUR")
        b = Amount(5.0, "USD")
        with pytest.raises(ValueError, match="Cannot add EUR and USD"):
            _ = a + b

    def test_add_negative_values(self) -> None:
        """Test adding amounts with negative values."""
        a = Amount(-10.0, "EUR")
        b = Amount(5.0, "EUR")
        result = a + b
        assert result.value == -5.0


class TestAmountSubtraction:
    """Tests for Amount.__sub__."""

    def test_subtract_same_currency(self) -> None:
        """Test subtracting two amounts with the same currency."""
        a = Amount(10.0, "EUR")
        b = Amount(3.0, "EUR")
        result = a - b
        assert result.value == 7.0
        assert result.currency == "EUR"

    def test_subtract_different_currency_raises(self) -> None:
        """Test that subtracting amounts with different currencies raises ValueError."""
        a = Amount(10.0, "EUR")
        b = Amount(5.0, "USD")
        with pytest.raises(ValueError, match="Cannot subtract USD from EUR"):
            _ = a - b

    def test_subtract_results_in_negative(self) -> None:
        """Test subtracting a larger amount from a smaller one."""
        a = Amount(5.0, "EUR")
        b = Amount(10.0, "EUR")
        result = a - b
        assert result.value == -5.0


class TestAmountNegation:
    """Tests for Amount.__neg__."""

    def test_negate_positive(self) -> None:
        """Test negating a positive amount."""
        a = Amount(10.0, "EUR")
        result = -a
        assert result.value == -10.0
        assert result.currency == "EUR"

    def test_negate_negative(self) -> None:
        """Test negating a negative amount."""
        a = Amount(-10.0, "EUR")
        result = -a
        assert result.value == 10.0

    def test_double_negation(self) -> None:
        """Test that double negation returns the original value."""
        a = Amount(10.0, "EUR")
        result = -(-a)
        assert result.value == a.value


class TestAmountMultiplication:
    """Tests for Amount.__mul__ and Amount.__rmul__."""

    def test_multiply_by_positive_scalar(self) -> None:
        """Test multiplying by a positive scalar."""
        a = Amount(10.0, "EUR")
        result = a * 2
        assert result.value == 20.0
        assert result.currency == "EUR"

    def test_multiply_by_negative_scalar(self) -> None:
        """Test multiplying by a negative scalar."""
        a = Amount(10.0, "EUR")
        result = a * -2
        assert result.value == -20.0

    def test_multiply_by_float(self) -> None:
        """Test multiplying by a float scalar."""
        a = Amount(10.0, "EUR")
        result = a * 0.5
        assert result.value == 5.0

    def test_reverse_multiply(self) -> None:
        """Test that scalar * amount works (rmul)."""
        a = Amount(10.0, "EUR")
        result = 2 * a
        assert result.value == 20.0
        assert result.currency == "EUR"


class TestAmountAbsolute:
    """Tests for Amount.__abs__."""

    def test_abs_positive(self) -> None:
        """Test absolute value of a positive amount."""
        a = Amount(10.0, "EUR")
        result = abs(a)
        assert result.value == 10.0
        assert result.currency == "EUR"

    def test_abs_negative(self) -> None:
        """Test absolute value of a negative amount."""
        a = Amount(-10.0, "EUR")
        result = abs(a)
        assert result.value == 10.0
        assert result.currency == "EUR"

    def test_abs_zero(self) -> None:
        """Test absolute value of zero."""
        a = Amount(0.0, "EUR")
        result = abs(a)
        assert result.value == 0.0
