"""Maps local account names to their source-scoped external id.

The external id (IBAN for banks, Swile wallet id) is declared once by the user
in configuration. File exports (e.g. BNP xls) carry no external id, so ingest
resolves it from this registry by the local account name.
"""
from collections.abc import Mapping


class AccountRegistry:  # pylint: disable=too-few-public-methods
    """Resolve the external id of a local account from its name."""

    def __init__(self, external_ids_by_name: Mapping[str, str] | None = None) -> None:
        self._external_ids_by_name = dict(external_ids_by_name or {})

    def external_id_for(self, name: str) -> str | None:
        """Return the declared external id for a local account name, if any."""
        return self._external_ids_by_name.get(name)
