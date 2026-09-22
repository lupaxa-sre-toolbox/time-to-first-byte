"""CLI entrypoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from lupaxa.time_to_first_byte.cli import (
    _program_name,
    build_parser,
    format_sample_line,
    format_summary,
    main,
)
from lupaxa.time_to_first_byte.measure import TimingResult, TimingSummary
from lupaxa.time_to_first_byte.version import get_version

_BASE = ["--url", "http://example.com/"]


def _result(*, ok: bool = True, sequence: int = 0) -> TimingResult:
    return TimingResult(
        ok=ok,
        url="https://example.com",
        sequence=sequence,
        dns_ms=4.12,
        connect_ms=18.40,
        tls_ms=32.11,
        ttfb_ms=96.55,
        status=200 if ok else None,
        redirects=0,
        final_url="https://www.example.com/" if ok else "https://example.com",
        detail="ok" if ok else "connection timed out",
    )


def _summary(*, failed: bool = False) -> TimingSummary:
    result = _result(ok=not failed)
    return TimingSummary(
        total=1,
        passed=0 if failed else 1,
        failed=1 if failed else 0,
        fail_percent=100.0 if failed else 0.0,
        ttfb_min_ms=None if failed else result.ttfb_ms,
        ttfb_avg_ms=None if failed else result.ttfb_ms,
        ttfb_max_ms=None if failed else result.ttfb_ms,
        results=(result,),
    )


def test_help_exits_zero_and_describes_url(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == 0
    assert "--url" in capsys.readouterr().out


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert get_version() in capsys.readouterr().out


def test_missing_url_exits_two() -> None:
    assert main([]) == 2


def test_parser_defaults() -> None:
    args = build_parser().parse_args(_BASE)
    assert args.url == "http://example.com/"
    assert args.delay == 1.0
    assert args.count is None
    assert args.timeout == 5.0
    assert args.max_redirects == 10


def test_parser_overrides() -> None:
    args = build_parser().parse_args(
        [
            *_BASE,
            "--delay",
            "0.25",
            "--count",
            "3",
            "--timeout",
            "2.5",
            "--max-redirects",
            "4",
        ],
    )
    assert args.delay == 0.25
    assert args.count == 3
    assert args.timeout == 2.5
    assert args.max_redirects == 4


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--timeout", "0"),
        ("--delay", "-1"),
        ("--count", "0"),
        ("--max-redirects", "-1"),
    ],
)
def test_parser_rejects_invalid_ranges(flag: str, value: str) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([*_BASE, flag, value])


def test_format_sample_lines() -> None:
    assert format_sample_line(_result()) == (
        "https://example.com seq=0 status=200 redirects=0 "
        "dns=4.12 ms connect=18.40 ms tls=32.11 ms ttfb=96.55 ms"
    )
    assert format_sample_line(_result(ok=False, sequence=1)) == (
        "https://example.com seq=1 error: connection timed out"
    )


def test_format_summary() -> None:
    summary = TimingSummary(
        total=5,
        passed=4,
        failed=1,
        fail_percent=20.0,
        ttfb_min_ms=80.1,
        ttfb_avg_ms=96.2,
        ttfb_max_ms=120.4,
        results=(),
    )
    assert format_summary(summary) == (
        "\nTTFB Results: Samples (Total/Pass/Fail): [5/4/1] (Failed: 20.00%) "
        "ttfb min/avg/max=80.10/96.20/120.40 ms"
    )


def test_format_all_fail_summary_omits_ttfb() -> None:
    summary = TimingSummary(2, 0, 2, 100.0, None, None, None, ())
    assert format_summary(summary) == (
        "\nTTFB Results: Samples (Total/Pass/Fail): [2/0/2] (Failed: 100.00%)"
    )


def test_main_success(capsys: pytest.CaptureFixture[str]) -> None:
    summary = _summary()

    def fake_run(*_args: object, **kwargs: object) -> TimingSummary:
        on_result = kwargs["on_result"]
        assert callable(on_result)
        on_result(summary.results[0])
        return summary

    with patch(
        "lupaxa.time_to_first_byte.cli.run_measurements",
        side_effect=fake_run,
    ) as run:
        assert main(["-u", "http://example.com/", "-c", "1"]) == 0
    run.assert_called_once()
    assert run.call_args.kwargs["count"] == 1
    output = capsys.readouterr().out
    assert format_sample_line(_result()) in output
    assert "[1/1/0]" in output


def test_main_failure_exits_one(capsys: pytest.CaptureFixture[str]) -> None:
    with patch(
        "lupaxa.time_to_first_byte.cli.run_measurements",
        return_value=_summary(failed=True),
    ):
        assert main(["-u", "http://example.com/", "-c", "1"]) == 1
    assert "[1/0/1]" in capsys.readouterr().out


def test_main_interrupt_exits_zero_immediately(capsys: pytest.CaptureFixture[str]) -> None:
    result = _result(ok=False)
    handlers: list[object] = []

    def capture(_signum: int, handler: object) -> object:
        handlers.append(handler)
        return lambda *_args: None

    def fake_run(*_args: object, **kwargs: object) -> None:
        on_result = kwargs["on_result"]
        assert callable(on_result)
        on_result(result)
        handler = handlers[-1]
        assert callable(handler)
        handler(2, None)

    with (
        patch("lupaxa.time_to_first_byte.cli.run_measurements", side_effect=fake_run),
        patch("lupaxa.time_to_first_byte.cli.signal.signal", side_effect=capture),
    ):
        assert main([*_BASE, "--count", "1"]) == 0
    output = capsys.readouterr().out
    assert output.count("TTFB Results:") == 1
    assert "[1/0/1]" in output


@pytest.mark.parametrize(
    ("argv0", "expected"),
    [
        ("/path/to/ttfb", "ttfb"),
        ("/path/to/__main__.py", "time-to-first-byte"),
    ],
)
def test_program_name(argv0: str, expected: str) -> None:
    assert _program_name(argv0) == expected


@pytest.mark.parametrize(
    ("argv0", "prefix"),
    [
        ("/path/to/__main__.py", "time-to-first-byte"),
        ("/path/to/ttfb", "ttfb"),
    ],
)
def test_value_error_uses_program_prefix(
    argv0: str,
    prefix: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch(
            "lupaxa.time_to_first_byte.cli.run_measurements",
            side_effect=ValueError("url scheme must be http or https"),
        ),
        patch("lupaxa.time_to_first_byte.cli.sys.argv", [argv0]),
    ):
        assert main(_BASE) == 1
    assert capsys.readouterr().err == f"{prefix}: url scheme must be http or https\n"
