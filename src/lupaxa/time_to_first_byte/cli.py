"""Command-line interface for Time to First Byte."""

from __future__ import annotations

import argparse
import math
import os
import signal
import sys
from types import FrameType

from .measure import (
    DEFAULT_DELAY,
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_TIMEOUT,
    TimingResult,
    TimingSummary,
    run_measurements,
    summarize,
)
from .version import get_version


def _positive_timeout(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be a number") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("timeout must be greater than 0")
    return timeout


def _non_negative_delay(value: str) -> float:
    try:
        delay = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("delay must be a number") from exc
    if not math.isfinite(delay) or delay < 0:
        raise argparse.ArgumentTypeError("delay must be 0 or greater")
    return delay


def _positive_count(value: str) -> int:
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("count must be an integer") from exc
    if count < 1:
        raise argparse.ArgumentTypeError("count must be greater than 0")
    return count


def _non_negative_redirects(value: str) -> int:
    try:
        redirects = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("max redirects must be an integer") from exc
    if redirects < 0:
        raise argparse.ArgumentTypeError("max redirects must be 0 or greater")
    return redirects


def _exit_code(exc: SystemExit) -> int:
    code = exc.code
    if code is None:
        return 0
    return code if isinstance(code, int) else 1


def _program_name(argv0: str) -> str:
    name = os.path.basename(argv0)
    return "time-to-first-byte" if name == "__main__.py" else name


def build_parser() -> argparse.ArgumentParser:
    """Build the ``time-to-first-byte`` argument parser."""
    parser = argparse.ArgumentParser(
        description="Measure HTTP time to first byte and repeat until interrupted.",
    )
    parser.add_argument(
        "-u",
        "--url",
        required=True,
        metavar="URL",
        help="HTTP or HTTPS URL",
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=_non_negative_delay,
        default=DEFAULT_DELAY,
        metavar="SECONDS",
        help=f"Delay between samples in seconds (default: {DEFAULT_DELAY:g})",
    )
    parser.add_argument(
        "-c",
        "--count",
        type=_positive_count,
        default=None,
        metavar="N",
        help="Number of samples (default: run until interrupted)",
    )
    parser.add_argument(
        "-T",
        "--timeout",
        type=_positive_timeout,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=f"Socket timeout in seconds (default: {DEFAULT_TIMEOUT:g})",
    )
    parser.add_argument(
        "--max-redirects",
        type=_non_negative_redirects,
        default=DEFAULT_MAX_REDIRECTS,
        metavar="N",
        help=f"Maximum redirects to follow (default: {DEFAULT_MAX_REDIRECTS})",
    )
    parser.add_argument("--version", action="version", version=get_version())
    return parser


def format_sample_line(result: TimingResult) -> str:
    """Return the output line for one timing sample."""
    if not result.ok:
        return f"{result.url} seq={result.sequence} error: {result.detail}"
    return (
        f"{result.url} seq={result.sequence} status={result.status} "
        f"redirects={result.redirects} dns={result.dns_ms:.2f} ms "
        f"connect={result.connect_ms:.2f} ms tls={result.tls_ms:.2f} ms "
        f"ttfb={result.ttfb_ms:.2f} ms"
    )


def format_summary(summary: TimingSummary) -> str:
    """Return the Ctrl-C / end-of-run results block."""
    text = (
        "\nTTFB Results: Samples (Total/Pass/Fail): "
        f"[{summary.total}/{summary.passed}/{summary.failed}] "
        f"(Failed: {summary.fail_percent:.2f}%)"
    )
    if summary.ttfb_min_ms is not None:
        text += (
            " ttfb min/avg/max="
            f"{summary.ttfb_min_ms:.2f}/{summary.ttfb_avg_ms:.2f}/"
            f"{summary.ttfb_max_ms:.2f} ms"
        )
    return text


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return _exit_code(exc)

    results: list[TimingResult] = []

    def _on_result(result: TimingResult) -> None:
        results.append(result)
        print(format_sample_line(result))

    def _on_interrupt(_signum: int, _frame: FrameType | None) -> None:
        print(format_summary(summarize(results)))
        raise SystemExit(0)

    previous = signal.signal(signal.SIGINT, _on_interrupt)
    try:
        summary = run_measurements(
            args.url,
            delay=args.delay,
            timeout=args.timeout,
            count=args.count,
            max_redirects=args.max_redirects,
            on_result=_on_result,
        )
    except SystemExit as exc:
        return _exit_code(exc)
    except ValueError as exc:
        print(f"{_program_name(sys.argv[0])}: {exc}", file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGINT, previous)

    print(format_summary(summary))
    return 0 if summary.failed == 0 else 1
