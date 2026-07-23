# Configuration

The application uses YAML configuration. A default configuration file is created on
first run at `~/.config/budget-forecaster/config.yaml`.

## Default Paths

| Resource      | Default path                                             |
| ------------- | -------------------------------------------------------- |
| Configuration | `~/.config/budget-forecaster/config.yaml`                |
| Database      | `~/.local/share/budget-forecaster/budget.db`             |
| Log file      | `~/.local/share/budget-forecaster/budget-forecaster.log` |
| Backups       | `~/.local/share/budget-forecaster/backups/`              |

All paths can be customized in the configuration file (see below).

## Configuration Structure

```yaml
# Required - SQLite database location
database_path: ~/.local/share/budget-forecaster/budget.db

# Required - Account identification
account_name: "Main Account"
account_currency: EUR

# Optional - Folder for bank exports (auto-detected from xdg-user-dir if omitted)
# inbox_path: ~/Downloads

# Optional - Filter imported files by filename patterns
# inbox_include_patterns:
#   - "*.xlsx"
# inbox_exclude_patterns:
#   - "*template*"

# Optional - Automatic database backups
backup:
  enabled: true # default: true
  max_backups: 5 # default: 5
  directory: ~/.local/share/budget-forecaster/backups/ # default: same as database

# Optional - Language for the UI and exports (default: en)
# language: fr

# Optional - Account registry: external id of each account (IBAN for banks,
# Swile wallet id). The name matches the adapter (bnp, swile).
# accounts:
#   - name: bnp
#     external_id: "FR76..."      # IBAN
#   - name: swile
#     external_id: "..."          # Swile wallet id

# Optional - Enable Banking API source (used by the `sync` command)
# enable_banking:
#   application_id: "your-application-id"
#   private_key_path: ~/.config/budget-forecaster/enable_banking_key.pem
#   redirect_url: "https://your-redirect-url"
#   aspsp_country: FR
#   aspsp_name: "the-bank-name"   # optional: skip the bank picker in `link`
#   account_uid: "..."            # optional: pick one when a consent has several
#   local_account_name: bnp       # local account the sync merges into

# Optional - Python dictConfig format for logging
# logging:
#   version: 1
#   handlers:
#     console:
#       class: logging.StreamHandler
#       level: DEBUG
#   root:
#     level: DEBUG
#     handlers: [console]
```

## Settings Reference

| Setting                  | Required | Default                | Description                                |
| ------------------------ | -------- | ---------------------- | ------------------------------------------ |
| `database_path`          | yes      | -                      | Path to the SQLite database file           |
| `account_name`           | yes      | -                      | Display name for the account               |
| `account_currency`       | yes      | -                      | Currency code (e.g., EUR)                  |
| `inbox_path`             | no       | User's Downloads dir   | Folder scanned for bank exports            |
| `inbox_include_patterns` | no       | _(all files)_          | Glob patterns to include from inbox        |
| `inbox_exclude_patterns` | no       | _(none)_               | Glob patterns to exclude from inbox        |
| `backup.enabled`         | no       | `true`                 | Enable automatic backups at startup        |
| `backup.max_backups`     | no       | `5`                    | Maximum backup files to retain             |
| `backup.directory`       | no       | _(database directory)_ | Where to store backup files                |
| `language`               | no       | `en`                   | UI and export language (`en` or `fr`)      |
| `logging`                | no       | basic INFO logging     | Python dictConfig format for logging setup |
| `accounts`               | no       | _(none)_               | External id (IBAN / Swile id) per account  |
| `enable_banking`         | no       | _(disabled)_           | Enable Banking credentials for `sync`      |

## Syncing bank data (Enable Banking)

The `sync` command imports transactions and the account balance directly from the bank
through Enable Banking, as an alternative to loading exported files.

Linking a bank needs a consent that the bank issues after you authenticate in a browser
(valid ~180 days for BNP; varies by bank). Authorize the bank once with `link`, then
sync as often as you like:

```bash
budget-forecaster link            # prints a URL; authenticate, paste back the code
budget-forecaster sync            # import transactions and balance
budget-forecaster consent-status  # show whether the consent is valid/expiring/expired
```

`link` lists the banks available in `aspsp_country` and lets you pick yours, so you
never type an exact bank name (set `aspsp_name` to skip the picker). It stores the
resulting session and its expiry outside the repo, under
`$XDG_STATE_HOME/budget-forecaster` (falling back to `~/.local/state`), readable only by
you. `sync` reads that stored consent, so you never paste an account id by hand.
`account_uid` is only needed to pick one account when a single consent unlocks several.
When the consent expires, run `link` again to renew it.

Re-running `sync` is safe: already-imported operations are skipped, and operations that
overlap with a manual file import are reconciled rather than duplicated.

When an account is declared in the `accounts` registry, its external id (the IBAN)
becomes its stable identity: file imports and API syncs of the same account reconcile by
that id, and several accounts of the same bank stay distinct. Accounts left undeclared
keep working, matched by their name.

Obtaining the `application_id`, private key and `redirect_url` requires a one-time
Enable Banking setup, documented separately.

## Inbox Auto-Detection

When `inbox_path` is omitted, the application uses `xdg-user-dir DOWNLOAD` to find the
user's Downloads directory. This works on most Linux distributions. On other systems,
set the path explicitly.

## Logging

The `logging` section accepts Python's
[dictConfig format](https://docs.python.org/3/library/logging.config.html#logging-config-dictschema).
When no logging configuration is provided, the application logs to
`~/.local/share/budget-forecaster/budget-forecaster.log` at `INFO` level. If the
provided configuration is invalid, the application falls back to basic `DEBUG`-level
console logging.
