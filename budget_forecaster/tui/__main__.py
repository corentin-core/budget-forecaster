"""Entry point for running the TUI directly.

Usage:
    python -m budget_forecaster.tui -c config.yaml
"""

import argparse
import sys
from pathlib import Path

from budget_forecaster.tui.app import run_app


def main() -> None:
    """Run the TUI application."""
    parser = argparse.ArgumentParser(description="Budget Forecaster TUI")
    parser.add_argument(
        "-c",
        "--config",
        help="Path to the configuration file",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    if not args.config.exists():
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    run_app(args.config)


if __name__ == "__main__":
    main()
