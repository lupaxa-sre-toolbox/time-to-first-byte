# Getting Started

## Requirements

- Python 3.13 or newer
- An HTTP or HTTPS URL you are allowed to measure
- No runtime dependencies beyond the standard library

## Install

```bash
pip install lupaxa-time-to-first-byte
ttfb --help
```

## First Run

```bash
ttfb --url https://example.com
```

Each successful sample prints the original URL, sequence, final HTTP status,
redirect count, and phase timings. Press Ctrl-C to stop and print the summary.
Use `time-to-first-byte` instead of `ttfb` if you prefer the full command name.

Module entry point:

```bash
python -m lupaxa.time_to_first_byte --version
```

### From Source (Development)

```bash
make init
make python-install-dev
time-to-first-byte --version
```

## Makefile Helpers

```bash
make init                 # clone makefile-skills into .makefiles/
make python-install-dev   # editable install with [dev]
make python-check         # lint + type + test
make mkdocs-serve         # local docs site
```
