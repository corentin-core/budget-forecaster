"""Validate user-supplied redirect / back targets to same-origin relative paths.

Browsers normalize several forms to an external destination — scheme-relative
"//host", backslash "/\\host", and control-char "/%09/host" (tab) — so a naive
startswith("/") check is not enough to prevent an open redirect.
"""

from urllib.parse import urlsplit


def safe_local_path(value: str | None, default: str) -> str:
    """Return value if it is a safe same-origin relative path, else default."""
    if not value:
        return default
    if any(char < " " for char in value):  # tab / newline / CR, etc.
        return default
    if "\\" in value:
        return default
    if not value.startswith("/") or value.startswith("//"):
        return default
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return default
    return value
