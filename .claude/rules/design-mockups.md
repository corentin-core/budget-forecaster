# Design Mockups

## UI Designs Require Mockups

**Why**: Text descriptions of interfaces are ambiguous. Mockups prevent
misunderstandings and make designs reviewable before implementation.

**Rule**: ALWAYS include ASCII art mockups when designing UI features.

### What to Include

1. **Visual layout** - Show the actual screen/modal structure
2. **Data examples** - Use realistic sample data, not placeholders
3. **Interaction states** - Show selected items, hover states, etc.
4. **Keyboard shortcuts** - List them in a table near the mockup

### Mockup Format

Use box-drawing characters for clean alignment:

```
┌─────────────────────────────────────────────────────┐
│ Modal Title                                         │
├─────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────┐ │
│ │ Inner panel content                             │ │
│ │ Line 2                                          │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ Description text here                               │
│                                                     │
│                         [Cancel]  [Confirm]         │
└─────────────────────────────────────────────────────┘
```

**Alignment tips:**

- Inner boxes start 2 chars after outer border (│ + space)
- Inner boxes end 2 chars before outer border (space + │)
- Use consistent width throughout the mockup

### Feature Explanations

Below each mockup, include:

- **Features** - Bullet list of what each element does
- **Interactions** - How the user interacts (keyboard, mouse)
- **Notes** - Edge cases, limitations, special behaviors

### Example

```markdown
## Category Selection Modal

### Mockup

┌──────────────────────────────────────────────────┐ │
┌──────────────────────────────────────────────┐ │ │ │ Operation to categorize │ │ │ │
02/01/2025 SUPERMARKET CARREFOUR -85.20 € │ │ │
└──────────────────────────────────────────────┘ │ │ │ │ ★ Groceries (suggestion)
[selected] │ │ Electricity │ │ Rent │
└──────────────────────────────────────────────────┘

**Features:**

- Shows operation details (date, description, amount)
- Pre-selects suggested category based on similar operations
- Keyboard navigation with arrow keys

**Interactions:**

| Key     | Action              |
| ------- | ------------------- |
| `↑`/`↓` | Navigate categories |
| `Enter` | Confirm selection   |
| `Esc`   | Cancel              |
```
