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
        end

        subgraph Operations
            HO[HistoricOperation]
            PO[PlannedOperation]
            BU[Budget]
            OL[OperationLink]
            OM[OperationMatcher]
        end

        subgraph Forecast
            FC[Forecast]
            FA[ForecastActualizer]
        end

        subgraph Primitives
            AM[Amount]
            TR[TimeRange]
            PTR[PeriodicTimeRange]
        end
    end

    subgraph Infrastructure
        BA[BankAdapters]
        SR[SqliteRepository]
    end

    TUI --> AS
    CLI --> AS
    AS --> FS
    AS --> IS
    AS --> OS
    AS --> OLS
    FS --> AF
    FS --> FA
    IS --> BA
    AS --> PA
    PA --> SR
```

## Module Responsibilities

### Services Layer

Orchestrates business logic and coordinates between domain objects.

| Component                | Responsibilities                                                                                                                                 |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **ApplicationService**   | Central orchestrator for TUI. Manages matcher cache, coordinates imports, categorization, and CRUD operations on planned operations and budgets. |
| **ForecastService**      | Loads forecast data, computes account analysis reports, provides aggregated statistics (monthly summaries, category totals).                     |
| **ImportService**        | Handles bank file imports via adapters. Manages inbox folder, deduplicates operations, calculates balance from exports.                          |
| **OperationService**     | CRUD for historic operations. Filtering, category suggestions, and aggregations.                                                                 |
| **OperationLinkService** | Bridges matchers and repository. Implements heuristic linking algorithm with scoring.                                                            |

### Domain Layer

#### Account Management

| Component             | Responsibilities                                                                                           |
| --------------------- | ---------------------------------------------------------------------------------------------------------- |
| **PersistentAccount** | Facade for multi-account management. Loads/saves accounts, merges imported operations, detects duplicates. |
| **AggregatedAccount** | Combines multiple accounts into a single view. Aggregates balances and operations.                         |
| **AccountForecaster** | Computes account state at any target date. Projects future balance using forecast operations.              |

#### Operations

| Component             | Responsibilities                                                                                                |
| --------------------- | --------------------------------------------------------------------------------------------------------------- |
| **HistoricOperation** | Completed bank transaction with unique ID, date, amount, description, category.                                 |
| **PlannedOperation**  | Expected recurring or one-time operation with time range and matcher.                                           |
| **Budget**            | Allocated amount for a category over a time period.                                                             |
| **OperationLink**     | Links a historic operation to a planned operation or budget iteration. Supports manual and automatic links.     |
| **OperationMatcher**  | Encodes matching rules. Scores operations by category, amount tolerance, date proximity, and description hints. |

#### Forecast

| Component              | Responsibilities                                                                                                       |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **Forecast**           | Container for planned operations and budgets.                                                                          |
| **ForecastActualizer** | Updates forecast based on actual operations and links. Handles late iterations, postponements, and budget consumption. |

#### Primitives

| Component             | Responsibilities                                        |
| --------------------- | ------------------------------------------------------- |
| **Amount**            | Immutable money value with currency.                    |
| **TimeRange**         | Single occurrence time period (start + duration).       |
| **PeriodicTimeRange** | Recurring time period with repetition until expiration. |

### Infrastructure Layer

| Component            | Responsibilities                                                            |
| -------------------- | --------------------------------------------------------------------------- |
| **BankAdapters**     | Parse bank export files (BNP, Swile). Extract account info and operations.  |
| **SqliteRepository** | Persistence layer. Implements repository interfaces for all domain objects. |

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
        +description
        +amount
        +category
        +time_range
    }

    class ForecastOperationRange {
        +id
        +matcher
    }

    class PlannedOperation {
        +id
        +description
        +amount
        +category
        +time_range
        +matcher
    }

    class Budget {
        +id
        +description
        +amount
        +category
        +time_range
        +matcher
    }

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
        +date
        +amount
        +category
    }

    class OperationLink {
        +id: OperationLinkId
        +operation_id: OperationId
        +link_type: LinkType
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
        +category_hint
        +amount_tolerance
        +description_hints
        +match()
        +matches()
    }

    HistoricOperation "1" -- "0..1" OperationLink : linked by
    OperationLink "many" -- "1" PlannedOperation : targets
    OperationLink "many" -- "1" Budget : targets
    PlannedOperation "1" *-- "1" OperationMatcher
    Budget "1" *-- "1" OperationMatcher
```

### Repository Interfaces

```mermaid
classDiagram
    class RepositoryInterface {
        <<interface>>
    }

    class BudgetRepositoryInterface {
        <<interface>>
        +get_budgets()
        +add_budget()
        +update_budget()
        +delete_budget()
    }

    class PlannedOperationRepositoryInterface {
        <<interface>>
        +get_planned_operations()
        +add_planned_operation()
        +update_planned_operation()
        +delete_planned_operation()
    }

    class AccountRepositoryInterface {
        <<interface>>
        +get_accounts()
        +upsert_account()
    }

    class OperationLinkRepositoryInterface {
        <<interface>>
        +get_operation_links()
        +add_operation_link()
        +delete_operation_link()
        +delete_links_for_target()
    }

    class SqliteRepository {
        +db_path
    }

    RepositoryInterface <|-- BudgetRepositoryInterface
    RepositoryInterface <|-- PlannedOperationRepositoryInterface
    RepositoryInterface <|-- AccountRepositoryInterface
    RepositoryInterface <|-- OperationLinkRepositoryInterface
    BudgetRepositoryInterface <|.. SqliteRepository
    PlannedOperationRepositoryInterface <|.. SqliteRepository
    AccountRepositoryInterface <|.. SqliteRepository
    OperationLinkRepositoryInterface <|.. SqliteRepository
```

## Data Flows

### Bank Import Flow

```mermaid
sequenceDiagram
    participant User
    participant TUI
    participant AppService as ApplicationService
    participant ImportService
    participant BankAdapter
    participant PersistentAccount
    participant LinkService as OperationLinkService
    participant Repository

    User->>TUI: Select bank file
    TUI->>AppService: import_file(path)
    AppService->>ImportService: import_file(path)
    ImportService->>BankAdapter: parse(file)
    BankAdapter-->>ImportService: AccountParameters + operations
    ImportService-->>AppService: AccountParameters + operations
    AppService->>PersistentAccount: upsert_account()
    PersistentAccount->>Repository: save operations
    AppService->>LinkService: create_heuristic_links(new_ops, matchers)
    LinkService->>Repository: save links
```

### Forecast Computation Flow

```mermaid
sequenceDiagram
    participant TUI
    participant AppService as ApplicationService
    participant ForecastService
    participant AccountForecaster
    participant ForecastActualizer
    participant Repository

    TUI->>AppService: compute_report(date_range)
    AppService->>ForecastService: load_forecast()
    ForecastService->>Repository: get planned operations + budgets
    Repository-->>ForecastService: Forecast
    AppService->>Repository: get operation links
    AppService->>ForecastActualizer: actualize(forecast, links)
    ForecastActualizer-->>AppService: actualized forecast
    AppService->>AccountForecaster: compute state at start_date
    AccountForecaster-->>AppService: Account state
    AppService-->>TUI: AccountAnalysisReport
```

### Categorization Flow

```mermaid
sequenceDiagram
    participant User
    participant TUI
    participant AppService as ApplicationService
    participant OperationService
    participant LinkService as OperationLinkService
    participant Repository

    User->>TUI: Assign category to operation
    TUI->>AppService: categorize_operations(ops, category)
    AppService->>OperationService: update_category(ops, category)
    OperationService->>Repository: update operations
    AppService->>LinkService: delete_heuristic_links(ops)
    LinkService->>Repository: delete links
    AppService->>LinkService: create_heuristic_links(ops, matchers)
    LinkService->>Repository: save new links
```

## Design Principles

### Domain Objects over Primitives

Use rich domain types instead of dictionaries or tuples:

- `OperationLink` instead of `dict[OperationId, IterationDate]`
- `Amount` instead of `float`
- `TimeRange` instead of `tuple[date, date]`

### Immutability by Default

Most domain objects are immutable (NamedTuple or frozen dataclass):

- `Account`, `Amount`, `Forecast`, `OperationLink` are NamedTuples
- Modifications return new instances via `replace()` methods

### Single Link per Operation

An operation can only link to ONE target iteration. This constraint:

- Simplifies the linking logic
- Prevents ambiguity in forecast actualization
- Enforced by UNIQUE constraint in database

### Manual Links Override Heuristics

When recalculating links:

- Manual links (user-created) are preserved
- Heuristic links (auto-created) are deleted and recalculated
- This allows users to correct wrong automatic matches

### Lazy Matcher Cache

ApplicationService caches matchers for performance:

- Loaded on first access
- Invalidated when targets are created/updated/deleted
- Provides O(1) lookup for heuristic linking

## Key Invariants

1. **Operation uniqueness**: Operations are deduplicated by (description, amount, date)
   hash
2. **Balance date ordering**: Account balance_date must be the most recent export date
3. **Link consistency**: Links are recalculated when their target is modified
4. **Forecast actualization**: Late iterations are postponed to tomorrow, not deleted
5. **Budget consumption**: Linked operations reduce remaining budget by their amount
