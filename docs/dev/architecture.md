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

## Module Responsibilities

### Services Layer

Orchestrates business logic and coordinates between domain objects.

| Component                | Responsibilities                                                                                         |
| ------------------------ | -------------------------------------------------------------------------------------------------------- |
| **ApplicationService**   | Central facade for TUI. Manages matcher cache, coordinates imports, categorization, and CRUD operations. |
| **ForecastService**      | Loads forecast data, computes reports, provides statistics (monthly summaries, category totals).         |
| **ImportService**        | Handles bank file imports. Manages inbox folder, deduplicates operations.                                |
| **OperationService**     | CRUD for historic operations. Filtering, category suggestions, aggregations.                             |
| **OperationLinkService** | Implements heuristic linking algorithm with scoring. Bridges matchers and repository.                    |

### Domain Layer

#### Account Management

| Component             | Responsibilities                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------ |
| **PersistentAccount** | Facade for multi-account management. Loads/saves accounts, detects duplicates.             |
| **AggregatedAccount** | Combines multiple bank accounts into a single view.                                        |
| **AccountForecaster** | Computes account state at any date (past reconstruction or future projection).             |
| **AccountAnalyzer**   | Generates analysis reports with balance evolution, budget statistics, category breakdowns. |

#### Operations

| Component                 | Responsibilities                                                                                       |
| ------------------------- | ------------------------------------------------------------------------------------------------------ |
| **HistoricOperation**     | Immutable record of a completed bank transaction.                                                      |
| **PlannedOperation**      | Expected recurring or one-time operation with matcher.                                                 |
| **Budget**                | Allocated amount for a category over a time period.                                                    |
| **OperationLink**         | Associates a historic operation to a planned operation or budget iteration.                            |
| **OperationMatcher**      | Scoring rules for matching operations (category, amount tolerance, date proximity, description hints). |
| **OperationsCategorizer** | Auto-categorizes operations based on forecast matchers.                                                |

#### Forecast

| Component              | Responsibilities                                                                             |
| ---------------------- | -------------------------------------------------------------------------------------------- |
| **Forecast**           | Immutable container (NamedTuple) for planned operations and budgets.                         |
| **ForecastActualizer** | Updates forecast based on links. Handles late iterations, postponements, budget consumption. |

#### Primitives

| Component     | Responsibilities                                    |
| ------------- | --------------------------------------------------- |
| **Amount**    | Immutable money value with currency.                |
| **TimeRange** | Time period abstractions (single, daily, periodic). |
| **Category**  | Enum of transaction categories.                     |

### Infrastructure Layer

| Component                   | Responsibilities                                                             |
| --------------------------- | ---------------------------------------------------------------------------- |
| **SqliteRepository**        | Persistence for all domain objects. Implements ISP-compliant interfaces.     |
| **BankAdapters**            | Parse bank export files (BNP Excel, Swile JSON). Auto-detection via factory. |
| **Config**                  | YAML configuration loading and logging setup.                                |
| **BackupService**           | Automatic database backups with rotation.                                    |
| **AccountAnalysisRenderer** | Excel export with charts (balance evolution, expense breakdown).             |

## Class Relationships

### Operation Hierarchy

```mermaid
classDiagram
    class OperationRangeInterface {
        <<interface>>
        +description
        +amount
        +category
        +time_range
        +amount_on_period()
    }

    class OperationRange {
        #description
        #amount
        #category
        #time_range
    }

    class ForecastOperationRange {
        +id
        +matcher
    }

    class PlannedOperation
    class Budget

    class HistoricOperation {
        +unique_id
        +date
        +description
        +amount
        +category
    }

    OperationRangeInterface <|.. OperationRange
    OperationRange <|-- ForecastOperationRange
    ForecastOperationRange <|-- PlannedOperation
    ForecastOperationRange <|-- Budget
    OperationRangeInterface <|.. HistoricOperation
```

### Linking System

```mermaid
classDiagram
    class HistoricOperation {
        +unique_id: OperationId
    }

    class OperationLink {
        +operation_id: OperationId
        +target_type: LinkType
        +target_id: TargetId
        +iteration_date: IterationDate
        +is_manual: bool
    }

    class PlannedOperation {
        +id: PlannedOperationId
        +matcher: OperationMatcher
    }

    class Budget {
        +id: BudgetId
        +matcher: OperationMatcher
    }

    class OperationMatcher {
        +category
        +amount_tolerance
        +date_tolerance
        +description_hints
        +matches()
    }

    HistoricOperation "1" -- "0..1" OperationLink : linked by
    OperationLink "*" -- "1" PlannedOperation : targets
    OperationLink "*" -- "1" Budget : targets
    PlannedOperation "1" *-- "1" OperationMatcher
    Budget "1" *-- "1" OperationMatcher
```

### Repository Interfaces (ISP)

```mermaid
classDiagram
    class RepositoryInterface {
        <<interface>>
        +initialize()
        +close()
    }

    class BudgetRepositoryInterface {
        <<interface>>
    }

    class PlannedOperationRepositoryInterface {
        <<interface>>
    }

    class AccountRepositoryInterface {
        <<interface>>
    }

    class OperationRepositoryInterface {
        <<interface>>
    }

    class OperationLinkRepositoryInterface {
        <<interface>>
    }

    class SqliteRepository

    RepositoryInterface <|-- BudgetRepositoryInterface
    RepositoryInterface <|-- PlannedOperationRepositoryInterface
    RepositoryInterface <|-- AccountRepositoryInterface
    RepositoryInterface <|-- OperationRepositoryInterface
    RepositoryInterface <|-- OperationLinkRepositoryInterface
    BudgetRepositoryInterface <|.. SqliteRepository
    PlannedOperationRepositoryInterface <|.. SqliteRepository
    AccountRepositoryInterface <|.. SqliteRepository
    OperationRepositoryInterface <|.. SqliteRepository
    OperationLinkRepositoryInterface <|.. SqliteRepository
```

## Data Flows

### Bank Import Flow

```mermaid
sequenceDiagram
    participant User
    participant TUI
    participant AppService
    participant ImportService
    participant BankAdapter
    participant PersistentAccount
    participant LinkService
    participant Repository

    User->>TUI: Select bank file
    TUI->>AppService: import_file(path)
    AppService->>ImportService: import_file(path)
    ImportService->>BankAdapter: parse(file)
    BankAdapter-->>ImportService: operations + balance
    ImportService->>PersistentAccount: upsert_account()
    PersistentAccount->>Repository: save operations
    AppService->>LinkService: create_heuristic_links()
    LinkService->>Repository: save links
```

### Forecast Computation Flow

```mermaid
sequenceDiagram
    participant TUI
    participant AppService
    participant ForecastService
    participant ForecastActualizer
    participant AccountAnalyzer
    participant AccountForecaster

    TUI->>AppService: compute_report(date_range)
    AppService->>ForecastService: load_forecast()
    AppService->>ForecastActualizer: actualize(forecast, links)
    ForecastActualizer-->>AppService: actualized forecast
    AppService->>AccountAnalyzer: compute_report()
    AccountAnalyzer->>AccountForecaster: project balance
    AccountAnalyzer-->>TUI: AccountAnalysisReport
```

### Categorization Flow

```mermaid
sequenceDiagram
    participant User
    participant TUI
    participant AppService
    participant OperationService
    participant LinkService

    User->>TUI: Assign category
    TUI->>AppService: categorize_operations()
    AppService->>OperationService: update category
    AppService->>LinkService: delete old heuristic links
    AppService->>LinkService: create new heuristic links
```

## Key Algorithms

### Heuristic Link Matching

When an operation is imported or categorized, the system attempts to link it to a
planned operation or budget:

1. **Filter candidates** by category match
2. **Score each candidate** based on:
   - Amount proximity (within tolerance ratio)
   - Date proximity (within tolerance days)
   - Description hint matches (substring matching)
3. **Select best match** if score exceeds threshold
4. **Determine iteration date** from the planned operation's time range

Manual links (user-created) are never overwritten by heuristic matching.

### Forecast Actualization

The ForecastActualizer adjusts planned operations based on actual data:

1. **Identify actualized iterations** - iterations with links to past operations
2. **Detect late iterations** - past iterations without links (within tolerance window)
3. **Postpone late iterations** - create one-time operations for tomorrow
4. **Advance periodic operations** - move start date past last actualized iteration
5. **Consume budgets** - reduce remaining amount based on linked operations

### Balance Projection

AccountForecaster computes account state at any target date:

- **Past dates**: Subtract operations between target and balance_date from current
  balance
- **Future dates**: Add projected operations from actualized forecast to current balance

Projected operations are generated daily from planned operations and budgets,
distributing amounts evenly across their time ranges.

## Configuration

The application uses YAML configuration with:

- **Database path**: SQLite file location
- **Inbox path**: Folder for bank exports (auto-import)
- **Backup settings**: Enable/disable, max backups, rotation
- **Logging**: Python dictConfig format for flexible logging setup

Default configuration is created on first run at
`~/.config/budget-forecaster/config.yaml`.
