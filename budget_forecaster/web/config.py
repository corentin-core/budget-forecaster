"""Resolve server-side web secrets: environment first, config file as fallback."""

import os
from typing import NamedTuple

from budget_forecaster.infrastructure.config import Config

ENV_SECRET_KEY = "BUDGET_WEB_SECRET_KEY"
ENV_PASSWORD_HASH = "BUDGET_WEB_PASSWORD_HASH"


class WebSecretsError(RuntimeError):
    """Raised when a required web secret is missing."""


class WebSecrets(NamedTuple):
    """The two secrets the web app needs to run."""

    secret_key: str
    password_hash: str


def resolve_web_secrets(config: Config) -> WebSecrets:
    """Read the cookie signing key and password hash, env taking precedence.

    Raises WebSecretsError if either is missing from both sources.
    """
    secret_key = os.environ.get(ENV_SECRET_KEY) or config.web.secret_key
    password_hash = os.environ.get(ENV_PASSWORD_HASH) or config.web.password_hash
    if not secret_key:
        raise WebSecretsError(
            f"Missing web secret key. Set {ENV_SECRET_KEY} or web.secret_key."
        )
    if not password_hash:
        raise WebSecretsError(
            f"Missing web password hash. Set {ENV_PASSWORD_HASH} or web.password_hash."
        )
    return WebSecrets(secret_key=secret_key, password_hash=password_hash)
