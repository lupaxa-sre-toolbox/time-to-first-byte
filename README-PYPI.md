<!-- markdownlint-disable -->
<p align="center">
  <a href="https://github.com/lupaxa-sre-toolbox">
    <img src="https://raw.githubusercontent.com/the-lupaxa-project/brand-assets/master/logos/organisations/sre-toolbox/readme-logo.png" alt="Project Logo" width="256"/><br/>
  </a>
</p>
<h3 align="center">
  The Lupaxa SRE Toolbox<br />
  Part of The Lupaxa Project
</h3>

<br />

# lupaxa-time-to-first-byte

Measure HTTP time to first byte and repeat until interrupted.

## Features

- Measure DNS, connection, TLS, and total time to first byte
- Follow redirects and report the final response status
- Repeat after a configurable delay (default 1 second)
- Use a 5 second socket timeout and follow up to 10 redirects by default
- Run a fixed `--count` or continue until Ctrl-C
- Treat any HTTP response with a first byte, including 4xx and 5xx, as a pass
- Use the `measure` and `run_measurements` library API
- Run with no dependencies beyond the Python standard library

## Installation

### From PyPI

```bash
pip install lupaxa-time-to-first-byte
```

### From source (development mode)

```bash
pip install -e ".[dev]"
```

Requires Python 3.13+. No runtime dependencies.

## Library quick start

```python
from lupaxa.time_to_first_byte import measure, run_measurements

one = measure("https://example.com")
print(one.ok, one.status, one.ttfb_ms)

summary = run_measurements("https://example.com", count=3, delay=0)
print(summary.total, summary.passed, summary.failed)
```

## CLI quick start

```bash
time-to-first-byte --help
time-to-first-byte --url https://example.com
ttfb -u https://example.com --count 5
ttfb -u https://example.com --delay 0 --timeout 5 --max-redirects 10
```

You can also run the CLI as a module:

```bash
python -m lupaxa.time_to_first_byte --help
python -m lupaxa.time_to_first_byte --version
```

## Options

- `--url`, `-u`: required HTTP or HTTPS URL
- `--delay`, `-d`: seconds between samples; default `1`
- `--count`, `-c`: number of samples; omitted means run until Ctrl-C
- `--timeout`, `-T`: socket timeout in seconds; default `5`
- `--max-redirects`: maximum redirects to follow; default `10`
- `--version`: print the package version

## Documentation

Online documentation:

[Documentation](https://time-to-first-byte.thelupaxaproject.org/)

Source repository:

[GitHub](https://github.com/lupaxa-sre-toolbox/time-to-first-byte)

### Serve docs locally

From a clone of the repository:

```bash
make mkdocs-serve
```

Then open the local URL printed by MkDocs in your browser.

## Development

Clone the repository and install with Make:

```bash
make init                # first-time makefile-skills checkout
make python-install-dev  # editable install with [dev]
make python-check        # lint, type-check, and test
```

<a href="https://github.com/the-lupaxa-project">
    <img src="https://raw.githubusercontent.com/the-lupaxa-project/brand-assets/master/logos/components/footer-for-child-orgs.svg" alt="The Lupaxa Project Footer" width="100%" />
</a>
