---
paths:
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/tests/**/*.py"
---

# Testing Standards

## Two-tier testing strategy

Both types of tests are required:

1. **Unit tests**: Test each component in isolation with mocks. Fast, precise, easy to
   debug.
2. **Integration tests**: Verify components work together correctly. Exercise the
   complete flow without mocks to catch interface mismatches.

Unit tests alone are NOT sufficient - integration tests catch bugs that mocks hide.

## Validate actual output, not just existence

```python
# BAD - only checks file exists
def test_export():
    exporter.export(data, "output.csv")
    assert Path("output.csv").exists()

# GOOD - validates actual content
def test_export():
    exporter.export(data, "output.csv")
    expected = Path("tests/fixtures/expected.csv").read_text()
    assert Path("output.csv").read_text() == expected
```

## Use fixtures for expected outputs

For features that generate files (CSV, Excel, JSON), include reference files in
`tests/fixtures/` and compare against them.

## Test style

**Use `tmp_path` fixture instead of `tempfile`**:

```python
# BAD - manual cleanup, verbose
def test_export():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        output_path = Path(f.name)
    try:
        exporter.export(data, output_path)
    finally:
        output_path.unlink()

# GOOD - pytest handles cleanup
def test_export(tmp_path: Path):
    output_path = tmp_path / "output.csv"
    exporter.export(data, output_path)
    assert output_path.exists()
```

**Use `parametrize` instead of loops**:

```python
# BAD - loop hides which case failed
def test_categorize():
    for label, expected in [("AMAZON", Category.SHOPPING), ("SNCF", Category.TRANSPORT)]:
        assert categorize(label) == expected

# GOOD - each case runs as individual test
@pytest.mark.parametrize("label,expected", [
    ("AMAZON", Category.SHOPPING),
    ("SNCF", Category.TRANSPORT),
], ids=["amazon", "sncf"])
def test_categorize(label: str, expected: Category):
    assert categorize(label) == expected
```

**Assert on structures, not item by item**:

```python
# BAD - verbose
assert operations[0].amount == Decimal("100")
assert operations[0].label == "Test"
assert operations[1].amount == Decimal("200")

# GOOD - compare entire structure
assert operations == (
    Operation(amount=Decimal("100"), label="Test"),
    Operation(amount=Decimal("200"), label="Other"),
)
```

**Don't test language guarantees**: No need to test that NamedTuple is immutable, etc.

## Avoid tautological tests

Tests should verify behavior, not implementation. Avoid tests that:

- Test `set.add()` / `set.clear()` / `list.append()` behavior
- Mock internal methods just to call them directly
- Verify that a method was called (mock assertions) without checking outcome

```python
# BAD - tests that set.add works
def test_toggle_adds_to_set():
    table._selected_ids.add(1)
    assert 1 in table._selected_ids  # Tautological

# BAD - excessive mocking to test private method
def test_toggle_selection():
    table.cursor_row = MagicMock(return_value=0)
    table._toggle_selection(op_id=1, row_index=0)  # Testing internals
    assert 1 in table._selected_ids

# GOOD - test user-facing behavior
async def test_toggle_selection_with_space():
    async with app.run_test() as pilot:
        await pilot.press("space")
        assert table.selected_count == 1
```

## TUI integration tests with Textual

For TUI features, use Textual's test framework instead of mocking:

```python
from textual.app import App, ComposeResult

class TestApp(App[None]):
    def compose(self) -> ComposeResult:
        yield MyWidget()

@pytest.mark.asyncio
async def test_keyboard_shortcut():
    app = TestApp()
    async with app.run_test() as pilot:
        widget = app.query_one(MyWidget)

        # Simulate user input
        await pilot.press("space")
        await pilot.press("ctrl+a")

        # Verify result
        assert widget.state == expected
```

Benefits:

- Tests real keyboard bindings
- Catches event handling bugs
- No mocking of internals
- Documents actual user interactions

---

For high-level testing principles, see `CLAUDE.md`.
