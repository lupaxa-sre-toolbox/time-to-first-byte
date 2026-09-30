<p align="center">
  <a href="https://github.com/lupaxa-sre-toolbox">
    <img src="https://raw.githubusercontent.com/the-lupaxa-project/brand-assets/master/logos/organisations/sre-toolbox/readme-logo.png" alt="SRE Toolbox" />
  </a>
</p>

<h1 align="center">Time to First Byte</h1>

Measure HTTP time to first byte and repeat until interrupted.

Requires Python 3.13 or newer. The runtime is the standard library
only.

## Install

```bash
pip install lupaxa-time-to-first-byte
time-to-first-byte --help
```

## CLI

`time-to-first-byte` and `ttfb` call the same entry point.

```bash
time-to-first-byte --url https://example.com --count 5
ttfb -u https://example.com --delay 1 --timeout 5
python -m lupaxa.time_to_first_byte --version
```

The tool resolves the host, connects, negotiates TLS for HTTPS, sends
a GET, and stops at the first response byte. It follows up to 10
redirects by default and repeats every second until Ctrl-C unless
`--count` is set.

`--timeout` bounds socket operations after address resolution (default
`5` seconds). DNS uses the system resolver and is not bounded by
`--timeout`. `--timeout` must be greater than `0`. `--delay` and
`--max-redirects` must be `0` or greater. `--count` must be greater
than `0` when set. The URL must use HTTP or HTTPS.

A passing sample prints the original URL, sequence, final status,
redirect count, and phase timings:

```text
https://example.com seq=0 status=200 redirects=0 dns=4.25 ms connect=18.50 ms tls=24.10 ms ttfb=53.75 ms
```

An HTTP 4xx or 5xx response is still a pass when the server returns a
first byte. The status is the HTTP response. Pass or fail is whether
the measurement completed.

A failed sample prints the original URL, sequence, and reason:

```text
https://example.com seq=0 error: connection timed out
```

At the end of `--count`, or after Ctrl-C, the command prints a
summary. `ttfb min/avg/max` uses passing samples only:

```text
TTFB Results: Samples (Total/Pass/Fail): [5/4/1] (Failed: 20.00%) ttfb min/avg/max=41.20/48.35/57.80 ms
```

`dns`, `connect`, and `tls` on a passing line are the final hop. `tls`
is `0` for plain HTTP. `ttfb` includes every followed redirect and
measures the whole sample through the first byte of the final
response.

### Flags

| Flag              | Default               | Description                          |
| :---------------- | :-------------------- | :----------------------------------- |
| `--url`, `-u`     | required              | HTTP or HTTPS URL                    |
| `--delay`, `-d`   | `1`                   | Seconds between samples              |
| `--count`, `-c`   | run until interrupted | Number of samples                    |
| `--timeout`, `-T` | `5`                   | Socket timeout in seconds            |
| `--max-redirects` | `10`                  | Maximum redirects to follow          |
| `--version`       | —                     | Print the package version and exit   |

### Exit Codes

| Code | When                                                                |
| :--- | :------------------------------------------------------------------ |
| `0`  | Help, version, Ctrl-C, or every sample in a finite run passed       |
| `1`  | A sample failed, or runtime input validation failed                 |
| `2`  | Command-line usage or argument parsing failed                       |

### Examples

Until Ctrl-C (one sample per second, then a summary):

```bash
ttfb --url https://example.com
```

Five samples (exit `0` when all pass, `1` when any fail):

```bash
time-to-first-byte --url https://example.com --count 5
```

Back-to-back samples (`--delay 0` is valid):

```bash
ttfb --url https://example.com --delay 0 --count 10
```

## Library

```python
from lupaxa.time_to_first_byte import measure, run_measurements

one = measure("https://example.com", timeout=5.0, max_redirects=10)
print(one.ok, one.status, one.ttfb_ms, one.final_url)

summary = run_measurements("https://example.com", count=3, delay=0)
print(summary.total, summary.passed, summary.failed, summary.ttfb_avg_ms)
```

`measure` returns one `TimingResult`: `ok`, `url`, `sequence`,
`dns_ms`, `connect_ms`, `tls_ms`, `ttfb_ms`, `status`, `redirects`,
`final_url`, and `detail`. Connection, TLS, HTTP, and redirect
failures come back as `ok=False` rather than raised exceptions.
Invalid URLs, timeouts, delays, counts, and redirect limits raise
`ValueError`.

`run_measurements` returns a `TimingSummary`: `total`, `passed`,
`failed`, `fail_percent`, `ttfb_min_ms`, `ttfb_avg_ms`, `ttfb_max_ms`,
and `results`. `count=None` repeats until `should_stop` or forever.
Minimum, average, and maximum TTFB use passing samples only.

## Development

```bash
make init
make python-install-dev
make python-check
```

<a href="https://github.com/the-lupaxa-project">
    <img src="https://raw.githubusercontent.com/the-lupaxa-project/brand-assets/master/logos/components/footer-for-child-orgs.svg" alt="The Lupaxa Project Footer" width="100%" />
</a>
