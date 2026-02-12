"""A module for representing amounts of money."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Amount:
    """An amount of money."""

    value: float
    currency: str = "EUR"

    def __repr__(self) -> str:
        return f"{self.value} {self.currency}"

    def __add__(self, other: "Amount") -> "Amount":
        """Add two amounts together."""
        if self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} and {other.currency}")
        return Amount(self.value + other.value, self.currency)

    def __sub__(self, other: "Amount") -> "Amount":
        """Subtract another amount from this one."""
        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract {other.currency} from {self.currency}")
        return Amount(self.value - other.value, self.currency)

    def __neg__(self) -> "Amount":
        """Return the negation of this amount."""
        return Amount(-self.value, self.currency)

    def __mul__(self, scalar: float) -> "Amount":
        """Multiply the amount by a scalar."""
        return Amount(self.value * scalar, self.currency)

    def __rmul__(self, scalar: float) -> "Amount":
        """Multiply the amount by a scalar (reverse)."""
        return Amount(self.value * scalar, self.currency)

    def __abs__(self) -> "Amount":
        """Return the absolute value of this amount."""
        return Amount(abs(self.value), self.currency)
