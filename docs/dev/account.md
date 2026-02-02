# Account Management

This document describes account management, balance projection, and the bank import
process.

## Components

```mermaid
classDiagram
    class PersistentAccount {
        -repository
        -aggregated_account
        +save()
        +load()
        +upsert_account()
        +replace_account()
    }

    class AggregatedAccount {
        -accounts
        -aggregated_account
        +account()
        +accounts()
        +update_account()
        +upsert_account()
    }

    class AccountForecaster {
        -account
        -forecast
        +__call__(target_date)
    }

    class AccountAnalyzer {
        -account
        -forecast
        -operation_links
        +compute_report()
        +compute_forecast()
        +compute_balance_evolution_per_day()
        +compute_budget_statistics()
    }

    class AccountAnalysisRenderer {
        +render_to_excel()
    }

    class Account {
        +balance
        +balance_date
        +currency
        +operations
    }

    PersistentAccount "1" *-- "1" AggregatedAccount
    PersistentAccount --> SqliteRepository : uses
    AggregatedAccount "1" *-- "*" Account
    AccountAnalyzer --> AccountForecaster : uses
    AccountAnalysisRenderer --> AccountAnalyzer : renders
```

| Component                   | Responsibilities                                                               |
| --------------------------- | ------------------------------------------------------------------------------ |
| **PersistentAccount**       | Facade for multi-account management. Loads/saves accounts, detects duplicates. |
| **AggregatedAccount**       | Combines multiple bank accounts into a single view.                            |
| **Account**                 | Single bank account with balance, date, and operations.                        |
| **AccountForecaster**       | Computes account state at any date (past or future).                           |
| **AccountAnalyzer**         | Generates analysis reports with statistics.                                    |
| **AccountAnalysisRenderer** | Excel export with charts.                                                      |

## Balance Projection

AccountForecaster computes account state at any target date:

- **Past dates**: Subtract operations between target and balance_date from current
  balance
- **Future dates**: Add projected operations from actualized forecast to current balance

Projected operations are generated daily from planned operations and budgets,
distributing amounts evenly across their time ranges.

```mermaid
graph LR
    subgraph Past
        P1[balance_date - N]
        P2[...]
        P3[balance_date]
    end

    subgraph Future
        F1[today]
        F2[...]
        F3[target_date]
    end

    P3 -->|current balance| F1
    F1 -->|+ projected ops| F3
    P1 -->|reconstruct| P3
```

## Bank Import Flow

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

The import process:

1. User selects a bank export file (BNP Excel or Swile JSON)
2. BankAdapter auto-detects format and parses the file
3. Operations are deduplicated against existing data
4. New operations are saved to the repository
5. Heuristic links are created for categorized operations
