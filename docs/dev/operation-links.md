# Operation Links - Developer Documentation

This document describes the architecture and implementation of the operation links
feature, which connects historic bank operations to planned operations or budgets.

## Architecture Overview

```mermaid
graph TB
    subgraph "Presentation Layer"
        TUI[TUI App]
        LinkTargetModal[LinkTargetModal]
        LinkIterationModal[LinkIterationModal]
        OperationTable[OperationTable]
    end

    subgraph "Service Layer"
        OLS[OperationLinkService]
        FS[ForecastService]
        IS[ImportService]
    end

    subgraph "Domain Layer"
        OM[OperationMatcher]
        OL[OperationLink]
        PO[PlannedOperation]
        B[Budget]
        HO[HistoricOperation]
    end

    subgraph "Persistence Layer"
        Repo[SqliteRepository]
        DB[(SQLite DB)]
    end

    TUI --> LinkTargetModal
    TUI --> LinkIterationModal
    TUI --> OperationTable
    TUI --> OLS
    TUI --> FS
    TUI --> IS

    LinkTargetModal --> OLS
    FS --> OLS
    IS --> OLS

    OLS --> OM
    OLS --> Repo
    FS --> OM

    OM --> OL
    OM --> PO
    OM --> B
    OM --> HO

    Repo --> DB
```

## Data Model

### Class Diagram

```mermaid
classDiagram
    class LinkType {
        <<StrEnum>>
        PLANNED_OPERATION = "planned_operation"
        BUDGET = "budget"
    }

    class OperationLink {
        <<NamedTuple>>
        +int id
        +int operation_unique_id
        +LinkType target_type
        +int target_id
        +datetime iteration_date
        +bool is_manual
    }

    class OperationMatcher {
        -OperationRange operation_range
        -tuple~OperationLink~ operation_links
        -timedelta approximation_date_range
        -float approximation_amount_ratio
        -set~str~ description_hints
        +match(operation) bool
        +match_heuristic(operation) bool
        +is_linked(operation) bool
    }

    class OperationLinkService {
        -OperationLinkRepositoryInterface repository
        +get_all_links() tuple~OperationLink~
        +upsert_link(link) void
        +delete_link(operation_unique_id) void
        +load_links_for_target(target) tuple~OperationLink~
        +create_heuristic_links(operations, matchers) tuple~OperationLink~
        +recalculate_links_for_target(target, operations) tuple~OperationLink~
    }

    class OperationLinkRepositoryInterface {
        <<interface>>
        +get_link_for_operation(unique_id) OperationLink?
        +get_all_links() tuple~OperationLink~
        +get_links_for_planned_operation(id) tuple~OperationLink~
        +get_links_for_budget(id) tuple~OperationLink~
        +upsert_link(link) void
        +delete_link(unique_id) void
        +delete_automatic_links_for_target(type, id) void
    }

    OperationLink --> LinkType
    OperationMatcher --> OperationLink
    OperationLinkService --> OperationLinkRepositoryInterface
    OperationLinkService --> OperationMatcher
```

### Database Schema

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

**Key constraints:**

- `UNIQUE(operation_unique_id)`: An operation can only have ONE link
- `target_type`: Either `"planned_operation"` or `"budget"`
- `is_manual`: Protects manual links from automatic recalculation

## Key Components

### OperationLink

Immutable NamedTuple representing a link between an operation and a target iteration.

```python
class OperationLink(NamedTuple):
    operation_unique_id: int
    target_type: LinkType
    target_id: int
    iteration_date: datetime
    is_manual: bool = False
    id: int | None = None
```

### OperationMatcher

Handles both link-based and heuristic matching. Links always take priority.

```python
def match(self, operation: HistoricOperation) -> bool:
    # 1. Check operation link first (always wins)
    if self.is_linked(operation):
        return True
    # 2. Fall back to heuristic matching
    return self.match_heuristic(operation)
```

### OperationLinkService

Orchestrates link lifecycle between matchers and repository.

**Responsibilities:**

| Method                           | Purpose                                        |
| -------------------------------- | ---------------------------------------------- |
| `get_all_links()`                | Fetch all links for display                    |
| `upsert_link()`                  | Create or update a link                        |
| `delete_link()`                  | Delete a link by operation ID                  |
| `load_links_for_target()`        | Load links for a specific target               |
| `create_heuristic_links()`       | Create automatic links for unlinked operations |
| `recalculate_links_for_target()` | Refresh links after target edit                |

### Match Score

The `compute_match_score()` function calculates match quality (0-100):

```python
def compute_match_score(
    operation: HistoricOperation,
    operation_range: OperationRange,
    iteration_date: datetime,
) -> float:
    score = 0.0

    # Amount: 40% (only for PlannedOperation, not Budget)
    if not isinstance(operation_range, Budget):
        # ... amount scoring logic

    # Date: 30%
    # ... date proximity scoring

    # Category: 20%
    if operation.category == operation_range.category:
        score += 20.0

    # Description: 10%
    # ... description hints scoring

    return score
```

**Note:** Budgets skip amount scoring because budget amounts represent totals, not
individual operation amounts.

## Data Flows

### 1. Import Operations

```mermaid
sequenceDiagram
    participant CLI as CLI/TUI
    participant IS as ImportService
    participant OLS as OperationLinkService
    participant Repo as Repository
    participant OM as OperationMatcher

    CLI->>IS: import_operations(file)
    IS->>Repo: save operations
    IS->>OLS: create_heuristic_links(operations, matchers)

    loop For each unlinked operation
        OLS->>Repo: get_link_for_operation(id)
        Repo-->>OLS: None

        loop For each matcher
            OLS->>OM: match_heuristic(operation)
            OM-->>OLS: True/False

            alt Match found
                OLS->>OLS: compute_match_score()
                Note over OLS: Track best match
            end
        end

        alt Best match exists
            OLS->>Repo: upsert_link(link)
        end
    end

    OLS-->>IS: created links
    IS-->>CLI: import result
```

### 2. Manual Linking (TUI)

```mermaid
sequenceDiagram
    participant User
    participant TUI as BudgetApp
    participant LTM as LinkTargetModal
    participant LIM as LinkIterationModal
    participant OLS as OperationLinkService
    participant Repo as Repository

    User->>TUI: Press L on operation
    TUI->>TUI: Get selected operation
    TUI->>OLS: get_all_links()
    OLS-->>TUI: current_link or None
    TUI->>LTM: push_screen(operation, current_link, targets)

    alt User selects "Supprimer le lien"
        LTM-->>TUI: "unlink"
        TUI->>OLS: delete_link(operation_id)
        OLS->>Repo: delete_link(operation_id)
    else User selects target
        LTM-->>TUI: selected_target
        TUI->>LIM: push_screen(operation, target)
        User->>LIM: Select iteration
        LIM-->>TUI: iteration_date
        TUI->>OLS: upsert_link(OperationLink)
        OLS->>Repo: upsert_link(link)
    else User cancels
        LTM-->>TUI: None
    end

    TUI->>TUI: refresh_screens()
```

### 3. Edit Planned Operation / Budget

```mermaid
sequenceDiagram
    participant User
    participant TUI as BudgetApp
    participant FS as ForecastService
    participant OLS as OperationLinkService
    participant Repo as Repository

    User->>TUI: Edit planned operation
    TUI->>FS: update_planned_operation(op)
    FS->>Repo: save planned operation

    FS->>OLS: recalculate_links_for_target(target, operations)
    OLS->>Repo: delete_automatic_links_for_target(type, id)
    Note over Repo: Manual links preserved

    OLS->>OLS: create_heuristic_links(operations, {target: matcher})
    OLS->>Repo: upsert_link() for each new match

    OLS-->>FS: new links
    FS-->>TUI: update complete
    TUI->>TUI: refresh_screens()
```

### 4. Forecast Calculation

```mermaid
sequenceDiagram
    participant CLI as CLI/TUI
    participant FS as ForecastService
    participant OLS as OperationLinkService
    participant AA as AccountAnalyzer
    participant FA as ForecastActualizer

    CLI->>FS: compute_report(start, end)
    FS->>OLS: get_all_links()
    OLS-->>FS: all links

    FS->>AA: new AccountAnalyzer(account, forecast, links)
    FS->>AA: compute_report(start, end)

    AA->>FA: ForecastActualizer(account, links)(forecast)
    Note over FA: Actualizes planned ops and budgets using links
    FA-->>AA: actualized forecast

    AA->>AA: compute balance evolution
    AA-->>FS: AccountAnalysisReport

    FS-->>CLI: report
```

## Link Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> Unlinked: Operation imported

    Unlinked --> AutoLinked: Heuristic match found
    Unlinked --> ManualLinked: User creates link

    AutoLinked --> Unlinked: Target edited (no match)
    AutoLinked --> AutoLinked: Target edited (still matches)
    AutoLinked --> ManualLinked: User creates manual link
    AutoLinked --> Unlinked: User deletes link

    ManualLinked --> Unlinked: User deletes link
    ManualLinked --> ManualLinked: Target edited (preserved)

    note right of AutoLinked: is_manual = false
    note right of ManualLinked: is_manual = true
```

**Key rules:**

- Manual links are never automatically deleted
- Automatic links are recalculated when their target is edited
- User can always override automatic links with manual ones

## Testing Strategy

### Unit Tests

| Component            | Coverage                          |
| -------------------- | --------------------------------- |
| OperationLink        | Dataclass, LinkType enum          |
| OperationMatcher     | Link priority, heuristic fallback |
| OperationLinkService | Service orchestration             |
| SqliteRepository     | Link CRUD, migration              |

### Integration Tests

| Component          | Coverage                |
| ------------------ | ----------------------- |
| ForecastActualizer | Links in actualization  |
| ImportService      | Heuristic link creation |

### Key Scenarios

1. **Link priority**: Linked operation matches even if heuristics fail
2. **Heuristic creation**: Unlinked operation gets automatic link on import
3. **Manual preservation**: Manual link survives target edit
4. **Recalculation**: Automatic links updated when target changes
5. **Forecast impact**: Linked iterations excluded from future forecast
