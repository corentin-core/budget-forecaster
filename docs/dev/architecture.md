# Architecture Overview

This document describes the high-level architecture of Budget Forecaster.

## Layer Diagram

```mermaid
graph TB
    subgraph Presentation
        TUI[Terminal UI]
        CLI[CLI Entry Point]
    end

    subgraph Services
        AS[ApplicationService]
        FS[ForecastService]
        IS[ImportService]
        OS[OperationService]
        OLS[OperationLinkService]
    end

    subgraph Domain
        subgraph Account
            PA[PersistentAccount]
            AA[AggregatedAccount]
            AF[AccountForecaster]
            AN[AccountAnalyzer]
        end

        subgraph Operations
            HO[HistoricOperation]
            PO[PlannedOperation]
            BU[Budget]
            OL[OperationLink]
            OM[OperationMatcher]
            OC[OperationsCategorizer]
        end

        subgraph Forecast
            FC[Forecast]
            FA[ForecastActualizer]
        end

        subgraph Primitives
            AM[Amount]
            TR[TimeRange]
            CAT[Category]
        end
    end

    subgraph Infrastructure
        BA[BankAdapters]
        SR[SqliteRepository]
        CFG[Config]
        BK[BackupService]
        RND[AccountAnalysisRenderer]
    end

    TUI --> AS
    CLI --> AS
    AS --> FS
    AS --> IS
    AS --> OS
    AS --> OLS
    FS --> FA
    FS --> AN
    IS --> BA
    AS --> PA
    PA --> SR
    AN --> AF
    CFG --> BK
```

## Key Invariants

- An operation cannot be linked to multiple targets
- Manual links are never overwritten by heuristic matching
- Balance projection is deterministic given the same inputs

## Configuration

The application uses YAML configuration with:

- **Database path**: SQLite file location
- **Inbox path**: Folder for bank exports (auto-import)
- **Backup settings**: Enable/disable, max backups, rotation
- **Logging**: Python dictConfig format for flexible logging setup

Default configuration is created on first run at
`~/.config/budget-forecaster/config.yaml`.

## Documentation Index

- [Operations & Linking](operations.md) - Operation hierarchy, linking system,
  categorization
- [Forecast](forecast.md) - Forecast structure, actualization algorithm
- [Account](account.md) - Account management, balance projection, bank import
- [Persistence](persistence.md) - Repository interfaces, service layer
