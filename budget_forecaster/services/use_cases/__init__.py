"""Use cases extracted from ApplicationService for single-responsibility."""

from budget_forecaster.services.use_cases.categorize_use_case import (
    CategorizeUseCase,
)
from budget_forecaster.services.use_cases.compute_forecast_use_case import (
    ComputeForecastUseCase,
)
from budget_forecaster.services.use_cases.import_use_case import ImportUseCase
from budget_forecaster.services.use_cases.manage_links_use_case import (
    ManageLinksUseCase,
)
from budget_forecaster.services.use_cases.manage_targets_use_case import (
    ManageTargetsUseCase,
)
from budget_forecaster.services.use_cases.matcher_cache import MatcherCache

__all__ = [
    "CategorizeUseCase",
    "ComputeForecastUseCase",
    "ImportUseCase",
    "ManageLinksUseCase",
    "ManageTargetsUseCase",
    "MatcherCache",
]
