"""Store guessed categories for the operations nobody has categorized."""

import logging

from budget_forecaster.core.types import LinkType
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.services.operation.auto_categorizer import auto_categorize
from budget_forecaster.services.use_cases.matcher_cache import MatcherCache

logger = logging.getLogger(__name__)


def categorize_pending_operations(
    persistent_account: PersistentAccount, matcher_cache: MatcherCache
) -> int:
    """Guess and save categories, before heuristic linking needs them.

    Returns the number of operations categorized.
    """
    planned_matchers = tuple(
        matcher
        for key, matcher in matcher_cache.get_matchers().items()
        if key.link_type == LinkType.PLANNED_OPERATION
    )
    if not (
        categorized := auto_categorize(
            persistent_account.account.operations, planned_matchers
        )
    ):
        return 0
    for operation in categorized:
        persistent_account.replace_operation(operation)
    persistent_account.save()
    # The aggregated view is built at load time: replacing operations leaves it stale.
    persistent_account.reload()
    logger.info("Categorized %d operations automatically", len(categorized))
    return len(categorized)
