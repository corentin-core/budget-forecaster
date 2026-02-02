# Persistence Layer

This document describes the repository pattern and service layer architecture.

## Repository Interfaces (ISP)

The repository layer follows the Interface Segregation Principle. Each entity has its
own interface, and `RepositoryInterface` is a facade that combines them all.

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

    RepositoryInterface --|> BudgetRepositoryInterface
    RepositoryInterface --|> PlannedOperationRepositoryInterface
    RepositoryInterface --|> AccountRepositoryInterface
    RepositoryInterface --|> OperationRepositoryInterface
    RepositoryInterface --|> OperationLinkRepositoryInterface
    RepositoryInterface <|.. SqliteRepository
```

| Interface                               | Responsibilities                             |
| --------------------------------------- | -------------------------------------------- |
| **BudgetRepositoryInterface**           | CRUD for budgets.                            |
| **PlannedOperationRepositoryInterface** | CRUD for planned operations.                 |
| **AccountRepositoryInterface**          | Account and aggregated account management.   |
| **OperationRepositoryInterface**        | Historic operation updates.                  |
| **OperationLinkRepositoryInterface**    | Link management (create, delete, query).     |
| **RepositoryInterface**                 | Facade combining all interfaces + lifecycle. |

### Why ISP?

Services can depend on only the interface they need:

- `OperationLinkService` depends on `OperationLinkRepositoryInterface`
- `ForecastService` depends on `BudgetRepositoryInterface` and
  `PlannedOperationRepositoryInterface`

This reduces coupling and makes testing easier.

## Service Layer

Services orchestrate business logic and coordinate between domain objects.

```mermaid
classDiagram
    class ApplicationService {
        -persistent_account
        -import_service
        -operation_service
        -forecast_service
        -operation_link_service
        +import_file()
        +categorize_operations()
        +compute_report()
    }

    class ForecastService {
        -account
        -repository
        +load_forecast()
        +compute_report()
        +get_monthly_summary()
    }

    class ImportService {
        -persistent_account
        -bank_adapter_factory
        +import_file()
        +import_from_inbox()
    }

    class OperationService {
        -account_manager
        +get_operations()
        +categorize_operation()
        +suggest_category()
    }

    class OperationLinkService {
        -repository
        +get_all_links()
        +create_heuristic_links()
        +delete_link()
    }

    ApplicationService "1" *-- "1" ForecastService
    ApplicationService "1" *-- "1" ImportService
    ApplicationService "1" *-- "1" OperationService
    ApplicationService "1" *-- "1" OperationLinkService
    ForecastService --> AccountAnalyzer : uses
    ForecastService --> ForecastActualizer : uses
    ImportService --> BankAdapterFactory : uses
```

| Service                  | Responsibilities                                                                          |
| ------------------------ | ----------------------------------------------------------------------------------------- |
| **ApplicationService**   | Central facade for TUI. Manages matcher cache, coordinates imports, categorization, CRUD. |
| **ForecastService**      | Loads forecast data, computes reports, provides statistics.                               |
| **ImportService**        | Handles bank file imports. Manages inbox folder, deduplicates operations.                 |
| **OperationService**     | CRUD for historic operations. Filtering, category suggestions.                            |
| **OperationLinkService** | Implements heuristic linking algorithm. Bridges matchers and repository.                  |

## Infrastructure Components

| Component                   | Responsibilities                                                 |
| --------------------------- | ---------------------------------------------------------------- |
| **SqliteRepository**        | SQLite implementation of all repository interfaces.              |
| **BankAdapters**            | Parse bank export files (BNP Excel, Swile JSON).                 |
| **Config**                  | YAML configuration loading and logging setup.                    |
| **BackupService**           | Automatic database backups with rotation.                        |
| **AccountAnalysisRenderer** | Excel export with charts (balance evolution, expense breakdown). |
