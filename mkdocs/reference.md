# Reference

## CLI Arguments

| Flag              | Default               | Description                                |
| :---------------- | :-------------------- | :----------------------------------------- |
| `--url`, `-u`     | required              | HTTP or HTTPS URL                          |
| `--delay`, `-d`   | `1`                   | Seconds between samples (`0` or more)      |
| `--count`, `-c`   | run until interrupted | Number of samples                          |
| `--timeout`, `-T` | `5`                   | Socket timeout in seconds                  |
| `--max-redirects` | `10`                  | Maximum redirects to follow (`0` or more)  |
| `--version`       | —                     | Print the package version and exit         |

The URL must use HTTP or HTTPS. `--timeout` must be greater than `0`, and
`--count` must be greater than `0` when present.

The timeout applies to socket operations after address resolution. DNS uses the
system resolver and is not bounded by `--timeout`.

## Exit Codes

| Code | When                                                                |
| :--- | :------------------------------------------------------------------ |
| `0`  | Help, version, Ctrl-C, or every sample in a finite run passed       |
| `1`  | A sample failed, or runtime input validation failed                 |
| `2`  | Command-line usage or argument parsing failed                       |

## Library

| Name                    | Meaning                                                                  |
| :---------------------- | :----------------------------------------------------------------------- |
| `measure`               | Measure one URL through the first response byte                          |
| `run_measurements`      | Repeat samples; `count=None` runs until stopped                          |
| `TimingResult`          | Frozen result with phases, status, redirects, final URL, and detail      |
| `TimingSummary`         | Frozen totals and passing-sample TTFB minimum, average, and maximum      |
| `DEFAULT_DELAY`         | Default inter-sample delay (`1.0`)                                       |
| `DEFAULT_TIMEOUT`       | Default socket timeout (`5.0`)                                           |
| `DEFAULT_MAX_REDIRECTS` | Default redirect limit (`10`)                                            |
| `get_version()`         | Return the package version string                                        |

`TimingResult` fields are `ok`, `url`, `sequence`, `dns_ms`, `connect_ms`,
`tls_ms`, `ttfb_ms`, `status`, `redirects`, `final_url`, and `detail`.
`TimingSummary` fields are `total`, `passed`, `failed`, `fail_percent`,
`ttfb_min_ms`, `ttfb_avg_ms`, `ttfb_max_ms`, and `results`.

Connection, TLS, HTTP, and redirect failures are returned as `ok=False` rather
than raised. Invalid URLs, timeouts, delays, counts, and redirect limits raise
`ValueError`.
