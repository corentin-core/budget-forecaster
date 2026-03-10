# TUI - Managing Planned Operations & Budgets

This document describes how to use the TUI interface for managing planned operations and
budgets: viewing, editing, and splitting.

## Overview

The TUI provides two sections for managing forecast elements:

- **Planned Operations**: Expected future transactions (salary, rent, subscriptions)
- **Budgets**: Spending limits over time periods (monthly groceries, quarterly
  utilities)

Both are accessible via the **Configuration** tab.

## Planned Operations Table

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Opérations planifiées              [Ajouter] [Modifier] [Scinder] [Supprimer]                   │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [Search...        ] [Category  v] [Active  v]  [Filter] [Reset]                                 │
├────┬─────────────────────┬──────────┬────────────┬────────────┬───────────┬───────────┬─────────┤
│ ID │ Description         │ Montant  │ Catégorie  │ Date       │ Période   │ Fin       │ Mots-cl.│
├────┼─────────────────────┼──────────┼────────────┼────────────┼───────────┼───────────┼─────────┤
│ 1  │ Salaire             │ 2500.00€ │ Salaire    │ 2025-01-28 │ 1 mois    │ -         │ VIRT    │
│►2  │ Loyer               │ -800.00€ │ Loyer      │ 2025-01-05 │ 1 mois    │ -         │ LOYER   │
│ 3  │ Électricité         │  -95.00€ │ Électricité│ 2025-01-15 │ 1 mois    │ -         │ EDF     │
└────┴─────────────────────┴──────────┴────────────┴────────────┴───────────┴───────────┴─────────┘
3 opération(s) planifiée(s)
```

### Actions

| Button    | Description                                 |
| --------- | ------------------------------------------- |
| Ajouter   | Create a new planned operation              |
| Modifier  | Edit the selected operation                 |
| Scinder   | Split operation from a date (periodic only) |
| Supprimer | Delete the selected operation               |

### Status Filter

The status dropdown lets you filter operations by their state:

| Status  | Description                          |
| ------- | ------------------------------------ |
| Active  | Current operations (not expired)     |
| Expired | Operations whose end date has passed |
| All     | All operations regardless of status  |

## Budgets Table

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Budgets                                [Ajouter] [Modifier] [Scinder] [Supprimer]               │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [Search...        ] [Category  v] [Active  v]  [Filter] [Reset]                                 │
├────┬─────────────────────┬──────────┬────────────┬────────────┬───────────┬───────────┬─────────┤
│ ID │ Description         │ Montant  │ Catégorie  │ Début      │ Durée     │ Période   │ Fin     │
├────┼─────────────────────┼──────────┼────────────┼────────────┼───────────┼───────────┼─────────┤
│ 1  │ Courses mensuelles  │ -400.00€ │ Courses    │ 2025-01-01 │ 1 mois    │ 1 mois    │ -       │
│►2  │ Carburant           │ -150.00€ │ Carburant  │ 2025-01-01 │ 1 mois    │ 1 mois    │ -       │
│ 3  │ Loisirs             │ -200.00€ │ Loisirs    │ 2025-01-01 │ 3 mois    │ 3 mois    │ -       │
└────┴─────────────────────┴──────────┴────────────┴────────────┴───────────┴───────────┴─────────┘
3 budget(s) configuré(s)
```

## Duration and Period Input

Duration and period fields use a **number + unit selector** that supports granular time
units:

```
│ Durée:    [1    ] [Mois         ▼]                  │
│ Période:  [1    ] [Mois         ▼]                  │
```

### Available Units

| Unit   | French   | Example use case                  |
| ------ | -------- | --------------------------------- |
| Days   | Jours    | Short-term budgets (e.g. 15 days) |
| Weeks  | Semaines | Biweekly operations               |
| Months | Mois     | Monthly budgets (default)         |
| Years  | Années   | Annual subscriptions              |

The unit selector defaults to **Months** for backwards compatibility with existing
budgets and operations. When editing an existing item, the unit is automatically
detected from the stored value.

## Splitting Operations and Budgets

The **Scinder** (Split) action allows you to modify a recurring planned operation or
budget starting from a specific date, while preserving the history before that date.

### When to Use Split

- Salary increase starting next month
- Rent change after lease renewal
- Budget adjustment after lifestyle change
- Subscription price change

### How Split Works

When you split an operation or budget:

1. The **original element is terminated** the day before the split date
2. A **new element is created** with modified values starting from the split date
3. All **existing links for iterations >= split date are migrated** to the new element

### Split Modal

```
┌───────────────────────────────────────────────────────────────┐
│ Scinder à partir d'une date                                   │
├───────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐   │
│ │ Salaire                                                 │   │
│ │ Actuellement: +2500.00 €, 1 month, monthly              │   │
│ │ Depuis: 28/01/2025                                      │   │
│ └─────────────────────────────────────────────────────────┘   │
│                                                               │
│ Première itération:  [ 2025-06-01 ]                           │
│ (i) Prochaine itération non ajustée                           │
│ ───────────────────────────────────────────────────────────── │
│ Montant:             [ 2700.0     ]                           │
│ Période:             [ 1    ] [Mois         ▼]                │
│                                                               │
│                                     [Annuler]  [Appliquer]    │
└───────────────────────────────────────────────────────────────┘
```

For budgets, an additional **Durée** (Duration) field is displayed:

```
│ Durée:               [ 1    ] [Mois         ▼]                │
```

### Split Workflow Example

**Scenario**: Your salary increases from €2500 to €2700 starting June 2025.

1. Select the "Salaire" planned operation
2. Click **Scinder**
3. Set split date: `2025-06-01` (first iteration with new amount)
4. Set new amount: `2700.0`
5. Keep period: 1 Months
6. Click **Appliquer**

**Result**:

- Original "Salaire" operation ends on 2025-05-31
- New "Salaire" operation starts on 2025-06-01 with €2700
- Links for June onwards are automatically migrated to the new operation

### Validation Rules

- Split date must be **after** the original start date
- Split date must correspond to a valid iteration
- Amount must be a valid number
- Duration and period must be positive integers

### Keyboard Shortcuts

| Key      | Action                       |
| -------- | ---------------------------- |
| `Enter`  | Validate and apply split     |
| `Escape` | Cancel and close modal       |
| `Tab`    | Navigate between form fields |

## Tips

- **Default split date**: The modal suggests the next non-adjusted iteration (first
  future iteration without a linked operation)
- **Preserve history**: Use split instead of edit when you want to keep historical
  values for reporting
- **Link migration**: Existing links for future iterations are automatically transferred
  to the new element
