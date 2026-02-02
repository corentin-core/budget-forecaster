# Configuration

The application uses YAML configuration with:

- **Database path**: SQLite file location
- **Inbox path**: Folder for bank exports (auto-import)
- **Backup settings**: Enable/disable, max backups, rotation
- **Logging**: Python dictConfig format for flexible logging setup

Default configuration is created on first run at
`~/.config/budget-forecaster/config.yaml`.
