<p align="center">
  <a href="https://github.com/lupaxa-sre-toolbox">
    <img src="https://raw.githubusercontent.com/the-lupaxa-project/brand-assets/master/logos/organisations/sre-toolbox/readme-logo.png" alt="SRE Toolbox" />
  </a>
</p>

<h1 align="center">Time to First Byte</h1>

Measure HTTP time to first byte and repeat until interrupted.

## Install

```bash
pip install lupaxa-time-to-first-byte
time-to-first-byte --help
```

## CLI

```bash
time-to-first-byte --url https://example.com --count 5
ttfb -u https://example.com --delay 1 --timeout 5
python -m lupaxa.time_to_first_byte --version
```

The tool resolves the host, connects, negotiates TLS for HTTPS, sends an HTTP
request, and measures the time until the first response byte. It follows up to
10 redirects by default and repeats every second until Ctrl-C unless `--count`
is set.

## Library

```python
from lupaxa.time_to_first_byte import measure, run_measurements

one = measure("https://example.com", timeout=5.0)
print(one.ok, one.status, one.ttfb_ms)

summary = run_measurements("https://example.com", count=3, delay=0)
print(summary.total, summary.passed, summary.failed)
```

## Development

```bash
make init
make python-install-dev
make python-check
make mkdocs-serve
```

## Documentation

The published guide is at
<https://time-to-first-byte.thelupaxaproject.org/>.

Site Markdown lives in `mkdocs/`.

<a href="https://github.com/the-lupaxa-project">
    <img src="https://raw.githubusercontent.com/the-lupaxa-project/brand-assets/master/logos/components/footer-for-child-orgs.svg" alt="The Lupaxa Project Footer" width="100%" />
</a>
