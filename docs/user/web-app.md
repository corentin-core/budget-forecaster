# Web app

A mobile-first web interface over the same budget database as the TUI. This first
version is read-only: it shows your balance, monthly review, operations ledger, trends,
and connection status. Editing, sync controls, and remote access over Tailscale come in
later versions.

## Running the app

The app is served by uvicorn as a factory:

```bash
uvicorn --factory budget_forecaster.web.app:create_app
```

By default it reads `config.yaml` from the working directory. Point it at another config
with an environment variable:

```bash
BUDGET_CONFIG=~/.config/budget-forecaster/config.yaml uvicorn --factory budget_forecaster.web.app:create_app
```

The app binds to `127.0.0.1:8000` by default. Open http://127.0.0.1:8000 and sign in
with the shared password.

## Authentication

Access is gated by a single shared password, so you and anyone you share it with reach
the same household budget. The password never leaves the server: each device just opens
the URL, lands on the login page, and types the password. There is nothing to install or
configure on the phones and PCs that connect.

The server needs two secrets: a signing key for the session cookie and the password
hash.

Generate the password hash once from your chosen password:

```bash
python -c "from budget_forecaster.web.auth import hash_password; print(hash_password('your-password'))"
```

Provide both secrets through the environment (recommended for a deployed server):

```bash
export BUDGET_WEB_SECRET_KEY="a-long-random-string"
export BUDGET_WEB_PASSWORD_HASH="pbkdf2_sha256$480000$...."
```

For local development you can instead put them in a `web:` section of the config file
(see Configuration). The environment always wins over the config file. The app refuses
to start if neither source provides both secrets.

## Sections

| Section    | What it shows                                                                           |
| ---------- | --------------------------------------------------------------------------------------- |
| Accueil    | Balance, available margin for the month, this-month expense health, upcoming operations |
| Mois       | Per-category planned vs actual for one month; switch months from the URL or the arrows  |
| Opérations | The full ledger, filterable by search text, category, month, and "uncategorized"        |
| Tendances  | Balance evolution over time and expense breakdown by category                           |
| Réglages   | Bank connection status, import inbox, and the margin threshold                          |

Navigation is a bottom bar on phones and a left sidebar on wider screens.

## Consent banner

When a bank connection is configured and its consent is expiring (within 14 days) or
already expired, a banner appears on every page with a link to Réglages. No banner shows
when the connection is valid or when Enable Banking is not configured.
