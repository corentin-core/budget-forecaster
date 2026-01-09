"""Services layer for budget forecaster.

This module provides business logic services that can be used by any UI
(TUI, GUI, Web). Services encapsulate operations on the domain model
and provide a clean API for presentation layers.
"""

from budget_forecaster.services.operation_service import (
    OperationFilter,
    OperationService,
)

__all__ = ["OperationService", "OperationFilter"]
