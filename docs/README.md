# Documentation

## Table of Contents

### User Documentation

Guides for end-users explaining how to use features.

| Document                                   | Description                              |
| ------------------------------------------ | ---------------------------------------- |
| [Backup](user/backup.md)                   | Automatic database backup configuration  |
| [Operation Links](user/operation-links.md) | Linking operations to forecasts          |
| [TUI Operations](user/tui-operations.md)   | Multi-selection, categorization, linking |

### Developer Documentation

Technical documentation for developers: architecture, data flows, APIs.

| Document                                            | Description                       |
| --------------------------------------------------- | --------------------------------- |
| [Operation Links](dev/operation-links.md)           | Links architecture and data model |
| [Forecast Calculation](dev/forecast-calculation.md) | Forecast system architecture      |

### Quality Documentation

Test scenarios in Given-When-Then format.

| Document                                                | Description                               |
| ------------------------------------------------------- | ----------------------------------------- |
| [Operation Links](quality/operation-links.md)           | Link creation, update, deletion scenarios |
| [Forecast Calculation](quality/forecast-calculation.md) | Actualization and budget scenarios        |

## Structure

```
docs/
├── user/                        # End-user documentation
│   ├── backup.md
│   ├── operation-links.md
│   └── tui-operations.md
├── dev/                         # Developer documentation
│   ├── forecast-calculation.md
│   └── operation-links.md
└── quality/                     # Test scenarios
    ├── forecast-calculation.md
    └── operation-links.md
```
