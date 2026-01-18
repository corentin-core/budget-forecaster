"""Service for orchestrating operation link lifecycle.

This module will contain the OperationLinkService class that bridges
the OperationMatcher (uses links in memory) and the OperationLinkRepository
(persists links in the database).

See issue #59 for the full implementation plan.
"""

from datetime import datetime, timedelta

from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_range import OperationRange


def compute_match_score(
    operation: HistoricOperation,
    operation_range: OperationRange,
    iteration_date: datetime,
    approximation_amount_ratio: float = 0.05,
    approximation_date_range: timedelta = timedelta(days=5),
    description_hints: set[str] | None = None,
) -> float:
    """Compute a match score (0-100) for an operation against a specific iteration.

    Uses the same criteria as OperationMatcher with weighted scoring:
    - Amount: 40% of score
    - Date: 30% of score
    - Category: 20% of score
    - Description: 10% of score

    Args:
        operation: The historic operation to score.
        operation_range: The operation range to match against.
        iteration_date: The date of the specific iteration.
        approximation_amount_ratio: Tolerance ratio for amount matching.
        approximation_date_range: Tolerance for date matching.
        description_hints: Keywords that must appear in operation descriptions.

    Returns:
        A score from 0 to 100 indicating match quality.
    """
    hints = description_hints or set()
    approx_date_days = approximation_date_range.days

    score = 0.0

    # Amount score (40%)
    if (planned_amount := abs(operation_range.amount)) > 0:
        amount_diff = abs(abs(operation.amount) - planned_amount) / planned_amount
        if amount_diff <= approximation_amount_ratio:
            score += 40.0  # Full score if within tolerance
        else:
            # Gradual decrease beyond tolerance
            score += max(0.0, 40.0 * (1 - (amount_diff - approximation_amount_ratio)))

    # Date score (30%) - distance to specific iteration
    if (days_diff := abs((operation.date - iteration_date).days)) <= approx_date_days:
        score += 30.0  # Full score if within tolerance
    else:
        # Gradual decrease: score drops to 0 at 30 days beyond tolerance
        score += max(0.0, 30.0 * (1 - (days_diff - approx_date_days) / 30))

    # Category score (20%)
    if operation.category == operation_range.category:
        score += 20.0

    # Description score (10%)
    if hints:
        if all(hint in operation.description for hint in hints):
            score += 10.0
    # If no hints are configured, we don't award description points
    # (this matches the existing match_description behavior)

    return score
