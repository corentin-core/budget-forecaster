# Automatic Database Backup

Budget Forecaster automatically creates backups of your SQLite database at each
application startup, providing a safety net against data corruption or accidental
deletion.

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

Backup files follow this naming convention:

```
{database_name}_{YYYY-MM-DD_HHMMSS}.db
```

For example, if your database is `budget.db`, backups will be named:

- `budget_2025-01-17_143022.db`
- `budget_2025-01-17_091500.db`
- `budget_2025-01-16_180045.db`

## Rotation Behavior

When the number of backups exceeds `max_backups`:

1. Existing backups are sorted by modification time
2. The oldest backups are deleted until only `max_backups` remain
3. The newest backups are always preserved

## Manual Restore

To restore from a backup:

1. Stop the application
2. Locate the backup file you want to restore
3. Copy it to replace your current database:

```bash
cp backups/budget_2025-01-17_143022.db budget.db
```

4. Restart the application

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
