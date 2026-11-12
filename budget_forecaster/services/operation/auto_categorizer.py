"""Guess the category of operations nobody has categorized by hand.

Sources are tried in order: a planned operation the operation fulfils, then
the user's own recent categorizations of the same payee, then built-in rules.
Only manual categories teach the history: a guess learning from guesses would
repeat its own mistakes.
"""

from collections import defaultdict
from typing import Final, Iterable

from budget_forecaster.core.types import Category, CategorySource
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.services.operation.bank_labels import label_signature
from budget_forecaster.services.operation.category_rules import rule_category
from budget_forecaster.services.operation.operation_matcher import OperationMatcher

HISTORY_DEPTH: Final = 5
"""How many of the latest manual categorizations of a payee are consulted."""

HISTORY_MIN_VOTES: Final = 3
"""Fewer manual categorizations than this teach nothing."""

_PayeeKey = tuple[str, bool]
"""A label signature, and whether the operation is an expense."""


def _payee_key(operation: HistoricOperation) -> _PayeeKey | None:
    if not (signature := label_signature(operation.description)):
        return None
    return signature, operation.amount < 0


def _history_categories(
    operations: Iterable[HistoricOperation],
) -> dict[_PayeeKey, Category]:
    """The category each payee's latest manual categorizations agree on."""
    votes: dict[_PayeeKey, list[HistoricOperation]] = defaultdict(list)
    for operation in operations:
        if (
            operation.is_categorized_by_hand
            and operation.category != Category.UNCATEGORIZED
            and (key := _payee_key(operation)) is not None
        ):
            votes[key].append(operation)

    agreed: dict[_PayeeKey, Category] = {}
    for key, voters in votes.items():
        latest = sorted(voters, key=lambda op: op.operation_date, reverse=True)
        categories = {op.category for op in latest[:HISTORY_DEPTH]}
        if len(latest) >= HISTORY_MIN_VOTES and len(categories) == 1:
            agreed[key] = categories.pop()
    return agreed


def _planned_category(
    operation: HistoricOperation, planned_matchers: Iterable[OperationMatcher]
) -> Category | None:
    """The category of the planned operations matching it, unless they disagree.

    A planned operation left uncategorized has no category to give.
    """
    categories = {
        matcher.operation_range.category
        for matcher in planned_matchers
        if matcher.operation_range.category != Category.UNCATEGORIZED
        and matcher.match_except_category(operation)
    }
    return categories.pop() if len(categories) == 1 else None


def auto_categorize(
    operations: tuple[HistoricOperation, ...],
    planned_matchers: tuple[OperationMatcher, ...],
) -> tuple[HistoricOperation, ...]:
    """Guess a category for each uncategorized operation not left so by hand.

    Returns only the operations that received a category.
    """
    history = _history_categories(operations)
    categorized: list[HistoricOperation] = []
    for operation in operations:
        if (
            operation.category != Category.UNCATEGORIZED
            or operation.is_categorized_by_hand
        ):
            continue
        key = _payee_key(operation)
        if (category := _planned_category(operation, planned_matchers)) is not None:
            source = CategorySource.PLANNED
        elif key is not None and (category := history.get(key)) is not None:
            source = CategorySource.HISTORY
        elif key is not None and (category := rule_category(key[0])) is not None:
            source = CategorySource.RULE
        else:
            continue
        categorized.append(operation.replace(category=category, category_source=source))
    return tuple(categorized)
