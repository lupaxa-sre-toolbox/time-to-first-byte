"""Allow ``python -m lupaxa.time_to_first_byte`` to run the CLI."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
