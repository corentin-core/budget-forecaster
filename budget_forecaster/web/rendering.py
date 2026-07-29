"""Template rendering helper injecting the nav section and consent alert
that every page's base layout needs."""

from datetime import date
from typing import Any

from fastapi import Request
from fastapi.responses import Response

from budget_forecaster.web.alerts import (
    consent_alert,
    swile_reconnect_alert,
    sync_failure_alert,
)


def render_template(
    request: Request,
    name: str,
    *,
    active: str,
    status_code: int = 200,
    **context: Any,
) -> Response:
    """Render a template with the shared nav + consent-banner context."""
    templates = request.app.state.templates
    ctx = {
        "active": active,
        "alert": consent_alert(request.app.state.consent_service),
        "sync_alert": sync_failure_alert(
            request.app.state.repository, request.app.state.consent_service
        ),
        "swile_alert": swile_reconnect_alert(request.app.state.repository),
        "today": date.today(),
        "uncat_count": request.app.state.app_service.count_uncategorized_operations(),
        **context,
    }
    if "overdue_count" not in ctx:
        # A page that already built the card passes its own count.
        ctx["overdue_count"] = request.app.state.app_service.count_overdue_iterations()
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)
