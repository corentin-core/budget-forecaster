"""HTTP client for the Enable Banking API.

Handles JWT (RS256) authentication and the endpoints needed to list banks,
open an authorization, create a session and read an account's transactions
and balances.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import jwt
import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.enablebanking.com"
_JWT_ISSUER = "enablebanking.com"
_JWT_AUDIENCE = "api.enablebanking.com"
_JWT_TTL = timedelta(hours=1)
_REQUEST_TIMEOUT = 30


class EnableBankingClient:
    """Client talking to the Enable Banking API for a single application."""

    def __init__(
        self,
        application_id: str,
        private_key_path: Path,
        redirect_url: str,
        base_url: str = _BASE_URL,
        session: requests.Session | None = None,
    ) -> None:
        self._application_id = application_id
        self._private_key = Path(private_key_path).expanduser().read_bytes()
        self._redirect_url = redirect_url
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()

    def list_aspsps(self, country: str = "FR") -> list[dict]:
        """List the banks (ASPSPs) available in a country."""
        return self._request("GET", "/aspsps", params={"country": country}).get(
            "aspsps", []
        )

    def start_authorization(
        self,
        aspsp_name: str,
        country: str,
        valid_until: str,
        state: str,
        psu_type: str = "personal",
    ) -> str:
        """Open an authorization and return the bank redirect URL.

        The user opens the returned URL, authenticates with the bank and is
        redirected back with a code to pass to create_session.
        """
        body = {
            "access": {"valid_until": valid_until},
            "aspsp": {"name": aspsp_name, "country": country},
            "state": state,
            "redirect_url": self._redirect_url,
            "psu_type": psu_type,
        }
        return self._request("POST", "/auth", json_body=body)["url"]

    def create_session(self, code: str) -> dict:
        """Exchange an authorization code for a session with account uids."""
        return self._request("POST", "/sessions", json_body={"code": code})

    def get_transactions(
        self, account_uid: str, date_from: date | None = None
    ) -> list[dict]:
        """Fetch all transactions of an account, following pagination."""
        params: dict[str, str] = {}
        if date_from is not None:
            params["date_from"] = date_from.isoformat()

        transactions: list[dict] = []
        continuation_key: str | None = None
        while True:
            page_params = dict(params)
            if continuation_key is not None:
                page_params["continuation_key"] = continuation_key
            page = self._request(
                "GET", f"/accounts/{account_uid}/transactions", params=page_params
            )
            transactions.extend(page.get("transactions", []))
            if not (continuation_key := page.get("continuation_key")):
                return transactions

    def get_balances(self, account_uid: str) -> list[dict]:
        """Fetch the balances of an account."""
        return self._request("GET", f"/accounts/{account_uid}/balances").get(
            "balances", []
        )

    def _build_jwt(self) -> str:
        """Build a short-lived RS256 token identifying the application."""
        now = datetime.now(timezone.utc)
        payload = {
            "iss": _JWT_ISSUER,
            "aud": _JWT_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + _JWT_TTL).timestamp()),
        }
        return jwt.encode(
            payload,
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._application_id},
        )

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        """Send an authenticated request and return the parsed JSON body."""
        headers = {"Authorization": f"Bearer {self._build_jwt()}"}
        response = self._session.request(
            method,
            f"{self._base_url}{path}",
            headers=headers,
            params=params,
            json=json_body,
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
