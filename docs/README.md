# Documentation

## Table of Contents

### User Documentation

Guides for end-users explaining how to use features.

| Document                                                        | Description                              |
| --------------------------------------------------------------- | ---------------------------------------- |
| [Backup](user/backup.md)                                        | Automatic database backup configuration  |
| [Forecast](user/forecast.md)                                    | Reading forecasts, statuses, balance     |
| [Operation Links](user/operation-links.md)                      | Linking operations to forecasts          |
| [TUI Operations](user/tui-operations.md)                        | Multi-selection, categorization, linking |
| [TUI Planned Operations & Budgets](user/tui-planned-budgets.md) | Viewing, editing, splitting forecasts    |

### Developer Documentation

Technical documentation for developers: architecture, data flows, APIs.

| Document                                                          | Description                                  |
| ----------------------------------------------------------------- | -------------------------------------------- |
| [Architecture](dev/architecture.md)                               | Layer diagram, overview                      |
| [Operations](dev/operations.md)                                   | Operation hierarchy, linking, categorization |
| [Forecast](dev/forecast.md)                                       | Forecast structure, actualization            |
| [Account](dev/account.md)                                         | Account management, balance projection       |
| [Planned Operations & Budgets](dev/planned-operations-budgets.md) | Split functionality, management operations   |
| [Persistence](dev/persistence.md)                                 | Repository interfaces, service layer         |
| [Configuration](dev/configuration.md)                             | YAML config, logging, backup settings        |
| [Contributing](dev/contributing.md)                               | Dev setup, conventions, testing              |

### Quality Documentation

Test scenarios in Given-When-Then format.

| Document                                                | Description                               |
| ------------------------------------------------------- | ----------------------------------------- |
| [Operation Links](quality/operation-links.md)           | Link creation, update, deletion scenarios |
| [Forecast Calculation](quality/forecast-calculation.md) | Actualization and budget scenarios        |
| [Split Operations](quality/split-operations.md)         | Split preservation, migration scenarios   |

## Structure

```
docs/
├── user/                        # End-user documentation
│   ├── backup.md
│   ├── forecast.md
│   ├── operation-links.md
│   ├── tui-operations.md
│   └── tui-planned-budgets.md
├── dev/                         # Developer documentation
│   ├── architecture.md
│   ├── operations.md
│   ├── forecast.md
│   ├── account.md
│   ├── planned-operations-budgets.md
│   ├── persistence.md
│   ├── configuration.md
│   └── contributing.md
└── quality/                     # Test scenarios
    ├── forecast-calculation.md
    ├── operation-links.md
    └── split-operations.md
```
