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

---

For high-level testing principles, see `CLAUDE.md`.
