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

Each interface handles CRUD for a specific entity. RepositoryInterface is the facade
that combines them all and adds lifecycle methods (initialize/close).

### Why ISP?

Services can depend on only the interface they need:

- `OperationLinkService` depends on `OperationLinkRepositoryInterface`
- `ForecastService` depends on `BudgetRepositoryInterface` and
  `PlannedOperationRepositoryInterface`

This reduces coupling and makes testing easier.

## Database Schema

```mermaid
erDiagram
    operations {
        int unique_id PK
        int account_id FK
        text description
        text category
        timestamp date
        real amount
        text currency
    }

    planned_operations {
        int id PK
        text description
        real amount
        text currency
        text category
        timestamp start_date
        int period_value
        text period_unit
        timestamp end_date
        text description_hints
        int approximation_date_days
        real approximation_amount_ratio
    }

    budgets {
        int id PK
        text description
        real amount
        text currency
        text category
        timestamp start_date
        int period_value
        text period_unit
        timestamp end_date
    }

    operation_links {
        int id PK
        int operation_unique_id FK,UK
        text target_type
        int target_id
        timestamp iteration_date
        bool is_manual
        timestamp created_at
    }

    operations ||--o| operation_links : "has (0..1)"
    planned_operations ||--o{ operation_links : "targeted by"
    budgets ||--o{ operation_links : "targeted by"
```

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
        +reload_forecast()
        +compute_report()
        +get_monthly_summary()
        +get_category_statistics()
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

ApplicationService is the central facade for the TUI, coordinating all operations and
caching matchers for efficient link creation. The other services handle specific
concerns: imports, forecasts, operations CRUD, and link management.
