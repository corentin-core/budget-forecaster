# Swile Export Bookmarklet

Export your Swile operations and wallets with a single click.

## Installation

1. Open `swile_bookmarklet.html` in your browser
2. Drag the "Swile Export" button to your bookmarks bar

## Usage

1. Log in to https://team.swile.co/
2. Click the bookmarklet
3. Move downloaded files to `swile/` and run:
   ```bash
   python -m budget_forecaster.main -c config.yaml load swile/
   ```

## Development

To modify the bookmarklet:

1. Edit `swile_export.js`
2. Regenerate the HTML:
   ```bash
   python scripts/build_swile_bookmarklet.py
   ```

## Files

| File                         | Description                                |
| ---------------------------- | ------------------------------------------ |
| `swile_export.js`            | Source code (readable, editable)           |
| `build_swile_bookmarklet.py` | Build script (minifies JS, generates HTML) |
| `swile_bookmarklet.html`     | Generated installation page                |
