# Database Backups

Budget Forecaster automatically creates backups of your SQLite database at each
application startup, and lets you manage backups from the web app: list, create,
preview, restore, download and delete. This is a safety net against data corruption or
accidental deletion.

## Overview

When the application starts, it:

1. Checks if backup is enabled in configuration
2. Creates a timestamped copy of the database file
3. Removes old backups exceeding the configured limit

Backups are created **before** any database operations, ensuring you always have a
recovery point.

## Configuration

Add a `backup` section to your `config.yaml`:

```yaml
backup:
  enabled: true # Enable/disable automatic backups (default: true)
  max_backups: 5 # Number of backups to keep (default: 5)
  directory: ./backups # Backup directory (default: same as database)
```

### Options

| Option        | Type    | Default       | Description                              |
| ------------- | ------- | ------------- | ---------------------------------------- |
| `enabled`     | boolean | `true`        | Enable or disable automatic backups      |
| `max_backups` | integer | `5`           | Maximum number of backup files to retain |
| `directory`   | string  | _(db folder)_ | Directory to store backup files          |

## Backup File Naming

Automatic backups follow this naming convention:

```text
{database_name}_{YYYY-MM-DD_HHMMSS_microseconds}.db
```

For example, if your database is `budget.db`, backups will be named:

- `budget_2025-01-17_143022_004512.db`
- `budget_2025-01-17_091500_781203.db`

Backups you create on demand carry a `manual` marker, and safety copies taken before a
restore carry a `prerestore` marker:

- `budget_manual_2025-01-17_143022_004512.db`
- `budget_prerestore_2025-01-17_143022_004512.db`

## Rotation Behavior

Automatic (startup), manual (on-demand) and pre-restore safety copies each rotate on
their own counter, keeping only their most recent few. A restore's safety copy therefore
never pushes out a manual backup you still want, and repeated restores cannot grow the
backup folder without bound.

## Managing Backups from the Web App

The **Backups** section on the Settings page lists your backups newest first. Each row
is tagged by kind — "Automatique" (taken at startup), "Manuelle" (created on demand), or
"Copie de sécurité" (taken just before a restore). From there you can:

- **Create a backup** on demand.
- **Restore** a backup. This opens a read-only preview first — the balance, operation
  count and latest operation date of the backup next to your current data, with the
  difference between them. Restoring is a deliberate second step behind that preview.
- **Download** a backup as a raw `.db` file.
- **Delete** a backup (a confirmation is required).

### What a restore does

Restoring replaces the live database with the chosen backup and takes effect
immediately, without restarting the app. Before replacing anything, it:

1. Takes a **safety copy** of the current data (shown in the list, tagged "Copie de
   sécurité").
2. Upgrades the backup to the current data format if it is older, so an old backup never
   leaves the app in a broken state.
3. Swaps the database in place and reloads the account and forecast.

Because the data is shared, a restore changes what **everyone** using the app sees.
After a successful restore, an **Undo** button restores that safety copy, returning to
the state you had just before.

If the daily sync happens to be running, a restore reports that a sync is in progress —
wait a moment and try again.

### Manual restore (fallback)

You can still restore by hand if the app is not running:

1. Stop the application.
2. Copy the chosen backup over your current database:

   ```bash
   cp budget_2025-01-17_143022_000000.db budget.db
   ```

3. Restart the application.

## Troubleshooting

### Backups not being created

- Verify `backup.enabled` is `true` (or not set, as it defaults to `true`)
- Check that the database file exists (no backup on first run)
- Ensure write permissions on the backup directory

### Permission errors

If you see permission errors in logs:

- Check that the backup directory is writable
- On shared systems, ensure your user owns the backup directory

### Disk space

Monitor your backup directory size. With large databases and frequent restarts, backups
can consume significant space. Adjust `max_backups` accordingly.

## Disabling Backups

To disable automatic backups:

```yaml
backup:
  enabled: false
```
