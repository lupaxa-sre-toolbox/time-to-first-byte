# Examples

## One URL Until Ctrl-C

```bash
ttfb --url https://example.com
```

The command samples every second. Press Ctrl-C to print the summary and exit.

## Five Samples

```bash
time-to-first-byte --url https://example.com --count 5
```

The process exits `0` when all five samples pass or `1` when any sample fails.

## Back-to-Back Samples

```bash
ttfb --url https://example.com --delay 0 --count 10
```

`--delay 0` runs samples back to back. The same flags work against a service on this machine.

## Library

```python
from lupaxa.time_to_first_byte import measure, run_measurements

one = measure("https://example.com", timeout=5.0)
print(one.status, one.redirects, f"{one.ttfb_ms:.2f} ms")

summary = run_measurements(
    "https://example.com",
    count=5,
    delay=0.25,
)
print(summary.total, summary.passed, summary.failed)
```
