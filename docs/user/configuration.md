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
