"""lupaxa.time_to_first_byte — measure HTTP time to first byte."""

from __future__ import annotations

from .measure import (
    DEFAULT_DELAY,
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_TIMEOUT,
    TimingResult,
    TimingSummary,
    measure,
    run_measurements,
)
from .version import __version__, get_version

__all__ = [
    "DEFAULT_DELAY",
    "DEFAULT_MAX_REDIRECTS",
    "DEFAULT_TIMEOUT",
    "TimingResult",
    "TimingSummary",
    "__version__",
    "get_version",
    "measure",
    "run_measurements",
]
