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

PersistentAccount is the entry point for account management, handling persistence and
duplicate detection on import. AggregatedAccount combines multiple bank accounts (e.g.,
checking + savings) into a unified view. AccountForecaster projects balance at any date
by combining historic operations with forecast data.

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

BankAdapter auto-detects the file format (BNP Excel or Swile JSON). Operations are
deduplicated against existing data before saving.
