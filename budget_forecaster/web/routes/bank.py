"""Bank enrollment over OAuth: pick a bank, bounce to it, capture the callback.

Consumes the Enable Banking consent backend; no API code here. The callback is
a GET the bank redirects to, so it fails closed: it completes only when the
returned state matches the one stashed at start (CSRF guard).
"""

import hmac
import logging
import secrets
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from itsdangerous import URLSafeTimedSerializer
from requests import RequestException

from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
)
from budget_forecaster.infrastructure.config import Config
from budget_forecaster.web.dependencies import get_config, get_consent_service
from budget_forecaster.web.enrollment import (
    Flash,
    PendingEnrollment,
    clear_pending,
    read_pending,
    set_flash,
    set_pending,
)
from budget_forecaster.web.rendering import render_template

logger = logging.getLogger("budget_forecaster")

router = APIRouter()


def _pending_serializer(request: Request) -> URLSafeTimedSerializer:
    return request.app.state.pending_serializer


def _flash_serializer(request: Request) -> URLSafeTimedSerializer:
    return request.app.state.flash_serializer


def _secure(request: Request) -> bool:
    return request.app.state.web_secrets.secure_cookies


@router.get("/settings/bank/link")
async def link_page(
    request: Request,
    consent_service: ConsentService | None = Depends(get_consent_service),
    config: Config = Depends(get_config),
) -> Response:
    """Show the bank picker, or a confirm step when the bank is already known.

    Renewal (a consent exists) and a configured aspsp_name both skip the picker;
    otherwise the available banks are listed for the user to choose.
    """
    if consent_service is None or config.enable_banking is None:
        return RedirectResponse(url="/settings", status_code=303)

    if (consent := consent_service.current_consent()) is not None:
        return _render_link(
            request,
            renew=True,
            bank_name=consent.aspsp_name,
            country=consent.aspsp_country,
        )

    country = config.enable_banking.aspsp_country
    if config.enable_banking.aspsp_name:
        return _render_link(
            request,
            renew=False,
            bank_name=config.enable_banking.aspsp_name,
            country=country,
        )
    return _render_link(
        request, renew=False, banks=consent_service.list_banks(country), country=country
    )


def _render_link(
    request: Request,
    *,
    renew: bool,
    country: str,
    bank_name: str | None = None,
    banks: tuple[dict[str, Any], ...] = (),
) -> Response:
    """Render the enrollment page in pick or single-bank mode."""
    return render_template(
        request,
        "bank_link.html",
        active="settings",
        renew=renew,
        bank_name=bank_name,
        banks=banks,
        country=country,
    )


@router.post("/settings/bank/link")
async def start_link(
    request: Request,
    consent_service: ConsentService | None = Depends(get_consent_service),
    config: Config = Depends(get_config),
) -> Response:
    """Validate the chosen bank, open an authorization, redirect to the bank."""
    if consent_service is None or config.enable_banking is None:
        return RedirectResponse(url="/settings", status_code=303)

    form = await request.form()
    aspsp_name = str(form.get("aspsp_name", "")).strip()
    country = str(form.get("country", config.enable_banking.aspsp_country)).strip()

    known = {bank["name"] for bank in consent_service.list_banks(country)}
    if aspsp_name not in known:
        logger.warning("Rejected enrollment for unknown bank %r", aspsp_name)
        return RedirectResponse(url="/settings/bank/link", status_code=303)

    return _redirect_to_bank(request, consent_service, aspsp_name, country)


@router.post("/settings/bank/renew")
async def renew_bank(
    request: Request,
    consent_service: ConsentService | None = Depends(get_consent_service),
) -> Response:
    """Re-authorize the currently linked bank, redirecting to it."""
    if (
        consent_service is None
        or (consent := consent_service.current_consent()) is None
    ):
        return RedirectResponse(url="/settings", status_code=303)
    return _redirect_to_bank(
        request, consent_service, consent.aspsp_name, consent.aspsp_country
    )


def _redirect_to_bank(
    request: Request,
    consent_service: ConsentService,
    aspsp_name: str,
    country: str,
) -> Response:
    """Start the authorization and stash the pending state for the callback."""
    state = secrets.token_urlsafe(16)
    url = consent_service.start_enrollment(aspsp_name, country, state=state)
    response = RedirectResponse(url=url, status_code=303)
    set_pending(
        response,
        _pending_serializer(request),
        PendingEnrollment(state, aspsp_name, country),
        secure=_secure(request),
    )
    return response


@router.get("/settings/bank/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    consent_service: ConsentService | None = Depends(get_consent_service),
) -> Response:
    """Complete enrollment from the bank redirect, then return to Réglages.

    Fails closed: any missing/mismatched state, or an error from the bank,
    ends without touching the consent. The pending cookie is cleared on every
    path so a captured code cannot be replayed.
    """
    response = RedirectResponse(url="/settings", status_code=303)
    clear_pending(response)
    pending = read_pending(request, _pending_serializer(request))
    flash_serializer = _flash_serializer(request)
    secure = _secure(request)

    if error or not code:
        set_flash(response, flash_serializer, Flash.CANCELLED, secure=secure)
        return response
    if (
        consent_service is None
        or not state
        or pending is None
        or not hmac.compare_digest(pending.state, state)
    ):
        logger.warning("Enrollment callback rejected: missing or mismatched state")
        set_flash(response, flash_serializer, Flash.ERROR, secure=secure)
        return response

    try:
        consent_service.complete_enrollment(code, pending.aspsp_name, pending.country)
    except (RequestException, KeyError, ValueError):
        logger.exception("Enrollment completion failed")
        set_flash(response, flash_serializer, Flash.ERROR, secure=secure)
        return response

    set_flash(response, flash_serializer, Flash.LINKED, secure=secure)
    return response
