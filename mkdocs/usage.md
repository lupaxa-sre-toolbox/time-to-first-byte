# Usage

Use `time-to-first-byte` or its `ttfb` alias. Both commands invoke the same
entry point.

## CLI Flags

| Flag              | Default               | Description                          |
| :---------------- | :-------------------- | :----------------------------------- |
| `--url`, `-u`     | required              | HTTP or HTTPS URL                    |
| `--delay`, `-d`   | `1`                   | Seconds between samples              |
| `--count`, `-c`   | run until interrupted | Number of samples                    |
| `--timeout`, `-T` | `5`                   | Socket timeout in seconds            |
| `--max-redirects` | `10`                  | Maximum redirects to follow          |
| `--version`       | —                     | Print the package version and exit   |

```bash
ttfb --url https://example.com --count 5
```

`--timeout` must be greater than `0`. `--delay` and `--max-redirects` must be
`0` or greater. `--count` must be greater than `0` when set.

## Output

A passing sample prints a line like:

```text
https://example.com seq=0 status=200 redirects=0 dns=4.25 ms connect=18.50 ms tls=24.10 ms ttfb=53.75 ms
```

An HTTP 4xx or 5xx response is still a pass when the server returns a first
byte. The status describes the HTTP response; pass or fail describes whether
the measurement completed.

A failed sample prints the original URL, sequence, and reason:

```text
https://example.com seq=0 error: connection timed out
```

At the end of `--count`, or after Ctrl-C, the command prints a summary:

```text
TTFB Results: Samples (Total/Pass/Fail): [5/4/1] (Failed: 20.00%) ttfb min/avg/max=41.20/48.35/57.80 ms
```

The `dns`, `connect`, and `tls` phases on a passing line are for the final hop.
The `ttfb` value includes every followed redirect and measures the whole sample
from its initial request through the first byte of the final response.

## Library

```python
from lupaxa.time_to_first_byte import measure, run_measurements

one = measure("https://example.com", timeout=5.0, max_redirects=10)
print(one.ok, one.status, one.ttfb_ms, one.final_url)

summary = run_measurements(
    "https://example.com",
    count=3,
    delay=0.25,
    timeout=5.0,
    max_redirects=10,
)
print(summary.passed, summary.failed, summary.ttfb_avg_ms)
```

Signatures:

```python
measure(
    url: str,
    *,
    timeout: float = 5.0,
    sequence: int = 0,
    max_redirects: int = 10,
) -> TimingResult

run_measurements(
    url: str,
    *,
    delay: float = 1.0,
    timeout: float = 5.0,
    count: int | None = None,
    max_redirects: int = 10,
    on_result: Callable[[TimingResult], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> TimingSummary
```
