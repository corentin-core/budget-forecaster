"""A module for representing amounts of money."""
from typing import NamedTuple


class Amount(NamedTuple):
    """An amount of money with currency."""

    value: float
    currency: str = "EUR"

    def __repr__(self) -> str:
        return f"{self.value} {self.currency}"
