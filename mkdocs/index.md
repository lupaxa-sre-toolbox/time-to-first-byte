# Time to First Byte

`lupaxa-time-to-first-byte` measures how long an HTTP or HTTPS request takes to
receive its first response byte. Each sample resolves the host, connects,
negotiates TLS when needed, sends the request, follows redirects, and reports
the final response.

```bash
pip install lupaxa-time-to-first-byte
ttfb --url https://example.com
```

A passing sample reports the final status and DNS, connection, TLS, and total
TTFB timings. The command repeats until Ctrl-C unless you set `--count`.
